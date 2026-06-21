#!/usr/bin/env python
"""
persona_test_server.py — 페르소나를 골라 개인화 대화를 로컬에서 시험하는 테스트 서버.

두 기능을 한 페이지에서:
  1) 개인화 미리보기(로컬·결정적, 백엔드 불필요): 선택한 페르소나의 vitals를
     vital_rules.run → personal_context.safe_block 으로 해석해, 답변에 결합될
     '📋 내 기록' 블록과 밴드 findings를 그대로 보여준다.
  2) 라이브 대화(프록시): 같은 페르소나의 agent_input_field_to_value를 실어
     RAG 서비스 엔드포인트(/api/service/conversations/{graph})로 SSE 스트리밍.
     → 백엔드가 동일 개인화 경로(service_routes→vital_rules.run)로 답변을 만든다.

사용:
  python persona_test_server.py                      # 기본: 클라우드 dev RAG 라이브 대화(gcloud 토큰 자동)
  python persona_test_server.py --preview            # 미리보기 전용(백엔드 미연결)
  python persona_test_server.py --rag-url http://127.0.0.1:8080   # 로컬 rag_server 프록시
  python persona_test_server.py --port 8770 --graph SUPERVISED_HYBRID_SEARCH

전제: 기본(클라우드)은 gcloud 로그인 필요. 로컬 대상은 rag_server.py 기동(PG+OPENAI_API_KEY,
RAG_TRUST_SECRET 미설정 시 트러스트 통과). 미리보기(--preview)는 백엔드 없이도 동작.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent
PERSONAS_PATH = REPO_ROOT / "test_personas" / "personas.json"

# 라이브 대화 기본 대상 — 클라우드 dev (gcloud 토큰 자동 부착). 환경변수로 덮어쓰기 가능.
CLOUD_DEV_URL = os.environ.get(
    "RAG_DEV_URL", "https://medical-rag-dev-716262961556.asia-northeast3.run.app")


# ── 페르소나 로딩 ────────────────────────────────────────────
def load_personas() -> dict:
    with open(PERSONAS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _persona_by_id(data: dict, pid: str) -> dict | None:
    for p in data.get("personas", []):
        if p.get("id") == pid:
            return p
    return None


# ── 개인화 미리보기 (로컬·결정적) ────────────────────────────
def compute_preview(persona: dict, query: str) -> dict:
    """페르소나 + 질의 → 개인화 미리보기.

    Returns: {findings:[{signal,label_user,clinical_label,match}], safe_block:str,
              summary:str, agent_input:{...}}
    원시 측정값은 findings에 미포함(밴드 라벨만) — 제품 정책과 동일.
    """
    import vital_rules as vr
    import personal_context as pc
    from vital_input import parse_agent_inputs

    agent_input = build_agent_input(persona)
    parsed = parse_agent_inputs(agent_input)
    vitals = parsed.get("vital_signs") or []

    raw = []
    if vitals:
        raw = vr.run(
            vitals[-1],
            locale=persona.get("locale", "KR"),
            population=persona.get("population", "adult"),
            context=persona.get("context", "clinic"),
        )
        if len(vitals) >= 3:  # 다회 측정 → 중립 추세 노트
            raw = list(raw) + vr.run_trends(vitals)
    # 환경(공기질) 비해석적 노트 결합 (5층 환경×건강)
    try:
        from env_rules import air_quality_finding
        aqf = air_quality_finding(parsed.get("air_quality"))
        if aqf:
            raw = list(raw) + [aqf]
    except Exception:
        pass

    findings = [{
        "signal": f.get("signal_key"),
        "label_user": f.get("label_user"),
        "clinical_label": f.get("clinical_label"),  # dev 미리보기에서만 노출(내부)
        "match": f.get("match"),
    } for f in raw]
    safe_block = ""
    try:
        safe_block = pc.safe_block(raw, query or "") or ""
    except Exception as e:
        safe_block = f"(safe_block 계산 오류: {e})"
    if findings:
        labels = ", ".join(f"{f['signal']}={f['label_user']}" for f in findings)
        summary = f"신호 {len(findings)}건: {labels}"
    else:
        summary = "밴드/환경 매칭 0 (fail-closed — 개인화 생략)"
    # 방향 2 미리보기: 옵션 활성화 시 LLM 프롬프트에 들어갈 비식별 맥락(밴드 라벨만)
    try:
        import personal_llm_context as _plc
        llm_context = _plc.preview_context(raw, query or "")
    except Exception:
        llm_context = ""
    return {
        "findings": findings,
        "safe_block": safe_block,
        "llm_context": llm_context,
        "summary": summary,
        "agent_input": agent_input,
        "chart": build_chart(persona),
        "profile": build_profile(persona),
    }


def build_agent_input(persona: dict) -> dict:
    """페르소나 → Run Graph agent_input_field_to_value 계약 형식."""
    vitals = persona.get("vitals") or []
    return {
        "Vital Signs": json.dumps(vitals, ensure_ascii=False) if vitals else "",
        "Air Quality Score": persona.get("air_quality") or "",
        "PHR": persona.get("phr") or "{}",
    }


# ── 측정 그래프 스펙 (신호별 표시범위 + 참고 구간) ───────────────
# 구간(zones)은 표시용 참고치. 점의 밴드(색)는 vital_rules가 권위 있게 분류한다.
_GAUGE = {
    "blood_pressure": {"label": "혈압", "unit": "mmHg", "field": "bps", "min": 90, "max": 190,
                       "zones": [("안정", 90, 120), ("주의", 120, 140), ("경고", 140, 190)],
                       "second": "bpd"},
    "spo2": {"label": "산소포화도", "unit": "%", "field": "spo2", "min": 85, "max": 100,
             "zones": [("경고", 85, 90), ("주의", 90, 95), ("안정", 95, 100)]},
    "body_temperature": {"label": "체온", "unit": "℃", "field": "fever", "min": 35.5, "max": 40,
                         "zones": [("안정", 35.5, 37.3), ("주의", 37.3, 38), ("경고", 38, 40)]},
    "bmi": {"label": "체질량지수", "unit": "", "field": "bmi", "min": 15, "max": 40,
            "zones": [("주의", 15, 18.5), ("안정", 18.5, 23), ("주의", 23, 30), ("경고", 30, 40)]},
    "heart_rate": {"label": "심박수", "unit": "bpm", "field": "bpm", "min": 40, "max": 120,
                   "zones": [("주의", 40, 60), ("안정", 60, 100), ("주의", 100, 120)]},
}

# 공인 밴드가 없는 측정 — 그래프엔 그리되 분류(색)는 하지 않는다(중립).
# (이완기 혈압은 혈압 차트의 보조선으로 이미 표시 → 별도 추가 안 함)
_PLAIN = {
    "stress": {"label": "스트레스 지수", "unit": "", "field": "stress", "min": 0, "max": 100},
}

# 전체 데이터 패널용 — 원시 측정 필드 표시명(개발 점검용 입력 데이터 뷰).
_RAW_FIELDS = [
    ("bps", "수축기 혈압", "mmHg"), ("bpd", "이완기 혈압", "mmHg"),
    ("bpm", "심박수", "bpm"), ("spo2", "산소포화도", "%"),
    ("fever", "체온", "℃"), ("bmi", "체질량지수", ""), ("stress", "스트레스 지수", ""),
]
_PHR_LABEL = {
    "meds": "복약", "dx": "진단 이력", "history": "병력", "checkup": "검진",
    "hba1c": "당화혈색소", "bmi_band": "비만 단계", "lifestyle": "생활습관",
    "pregnancy": "임신", "status": "상태", "breastfeeding": "수유", "ldl": "LDL", "sensitive": "민감 이력",
}


def _classify_point(signal: str, reading: dict, *, locale="KR", population="adult", context="clinic"):
    """측정 1건 → (그래프 y값, 밴드 라벨|None). 밴드는 vital_rules 권위 분류(인구집단 반영)."""
    import vital_rules as vr
    kw = dict(locale=locale, population=population, context=context)
    if signal == "blood_pressure":
        bps, bpd = reading.get("bps"), reading.get("bpd")
        if not (isinstance(bps, (int, float)) and isinstance(bpd, (int, float))):
            return None, None
        b = vr.lookup_band("blood_pressure", {"systolic": bps, "diastolic": bpd}, **kw)
        return bps, (b["label_user"] if b["match"] == "ok" else None)
    field = _GAUGE[signal]["field"]
    v = reading.get(field)
    if not isinstance(v, (int, float)):
        return None, None
    b = vr.lookup_band(signal, v, **kw)
    return v, (b["label_user"] if b["match"] == "ok" else None)


def build_chart(persona: dict) -> dict:
    """페르소나 → 신호별 시계열 차트 스펙(원시값은 점 좌표로만, 라벨=밴드 색)."""
    vitals = persona.get("vitals") or []
    series = []
    for signal, spec in _GAUGE.items():
        points, second, present = [], [], False
        for r in vitals:
            if not isinstance(r, dict):
                continue
            v, band = _classify_point(signal, r, locale=persona.get("locale", "KR"),
                                      population=persona.get("population", "adult"),
                                      context=persona.get("context", "clinic"))
            if v is None:
                continue
            present = True
            t = (str(r.get("create_date") or ""))[5:10]  # MM-DD
            points.append({"t": t, "v": v, "band": band})
            if signal == "blood_pressure" and isinstance(r.get("bpd"), (int, float)):
                second.append({"t": t, "v": r["bpd"]})
        if not present:
            continue
        series.append({
            "signal": signal, "label": spec["label"], "unit": spec["unit"],
            "min": spec["min"], "max": spec["max"],
            "zones": [{"band": z[0], "from": z[1], "to": z[2]} for z in spec["zones"]],
            "points": points, "second": second,
        })
    # 무밴드 수치(스트레스·이완기 등) — 중립 그래프(색/구간 없음)
    for signal, spec in _PLAIN.items():
        points, present = [], False
        for r in vitals:
            if not isinstance(r, dict):
                continue
            v = r.get(spec["field"])
            if not isinstance(v, (int, float)):
                continue
            present = True
            points.append({"t": (str(r.get("create_date") or ""))[5:10], "v": v, "band": None})
        if present:
            series.append({"signal": signal, "label": spec["label"], "unit": spec["unit"],
                           "min": spec["min"], "max": spec["max"], "zones": [],
                           "points": points, "second": []})
    return {"series": series}


def build_profile(persona: dict) -> dict:
    """페르소나의 전체 입력 데이터(개발 점검용) — 원시 측정·PHR·환경·태그."""
    vitals = persona.get("vitals") or []
    latest = vitals[-1] if isinstance(vitals[-1], dict) else {} if vitals else {}
    measures = [{"label": l, "value": latest.get(k), "unit": u}
                for k, l, u in _RAW_FIELDS if isinstance(latest.get(k), (int, float))]
    phr_raw = persona.get("phr")
    try:
        phr = json.loads(phr_raw) if isinstance(phr_raw, str) and phr_raw.strip() else (phr_raw or {})
    except Exception:
        phr = {}
    phr_rows = []
    if isinstance(phr, dict):
        for k, v in phr.items():
            val = ", ".join(map(str, v)) if isinstance(v, list) else (
                "예" if v is True else ("아니오" if v is False else str(v)))
            phr_rows.append({"label": _PHR_LABEL.get(k, k), "value": val})
    return {
        "measures": measures,
        "phr": phr_rows,
        "air_quality": persona.get("air_quality") or "",
        "tags": persona.get("tags") or [],
        "readings": len(vitals),
    }


# ── 클라우드 토큰(선택) ──────────────────────────────────────
_token = {"v": None, "at": 0.0}


def get_id_token(force=False):
    now = time.time()
    if not force and _token["v"] and now - _token["at"] < 2400:
        return _token["v"]
    try:
        out = subprocess.run("gcloud auth print-identity-token", shell=True,
                             capture_output=True, text=True, timeout=30)
        tok = (out.stdout or "").strip()
        if tok:
            _token.update(v=tok, at=now)
        return tok or None
    except Exception as e:
        sys.stderr.write(f"[token] {e}\n")
        return None


def _headers(rag_url: str) -> dict:
    h = {
        "Content-Type": "application/json",
        "X-User-Id": "persona-tester",
        "X-User-Name": quote("페르소나테스터"),
        "X-User-Role": "tester",
        "X-User-Permissions": "manage_kb",
    }
    secret = os.environ.get("RAG_TRUST_SECRET")
    if secret:
        h["X-Rag-Trust"] = secret
    if ".run.app" in rag_url:  # 클라우드 대상이면 IAM 토큰
        tok = get_id_token()
        if tok:
            h["Authorization"] = "Bearer " + tok
    return h


# ── HTML ─────────────────────────────────────────────────────
PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>페르소나 개인화 테스트</title>
<style>
 body{font-family:system-ui,'Malgun Gothic',sans-serif;max-width:980px;margin:18px auto;padding:0 16px;color:#1c1c1c}
 h1{font-size:19px;margin:0 0 2px} .sub{color:#888;font-size:12px;margin-bottom:14px}
 .wrap{display:grid;grid-template-columns:300px 1fr;gap:16px;align-items:start}
 .card{border:1px solid #e2e6ea;border-radius:10px;padding:12px}
 select{width:100%;padding:8px;border:1px solid #ccc;border-radius:8px;font-size:14px}
 .pf{font-size:13px;color:#444;margin:8px 0}
 .tags span{display:inline-block;background:#eef3f8;color:#3a5a78;border-radius:10px;padding:1px 8px;font-size:11px;margin:2px 3px 0 0}
 .pv{margin-top:10px;border-top:1px dashed #e0e0e0;padding-top:8px}
 .pv h3{font-size:12px;color:#1f4e79;margin:6px 0 4px}
 .band{font-size:12px;margin:2px 0}
 .b0{color:#2e7d32}.b1{color:#b06a00}.b2{color:#c62828;font-weight:600}
 .blk{background:#f6f8fb;border:1px solid #e0e6ee;border-radius:8px;padding:8px;font-size:12px;white-space:pre-wrap;margin-top:4px}
 .dev{color:#aaa;font-size:11px}
 #log{border:1px solid #e2e6ea;border-radius:10px;padding:12px;min-height:300px;line-height:1.5}
 .u{color:#0a58ca;font-weight:600;margin-top:10px;white-space:pre-wrap}
 .a{color:#111;margin:4px 0 10px} .a h2{font-size:15px;margin:12px 0 6px;border-bottom:1px solid #eee}
 .a p{margin:4px 0} .a ul{margin:4px 0 8px;padding-left:20px} .a strong{font-weight:700}
 .pblk{background:#eef7ee;border:1px solid #bfe0bf;border-radius:8px;padding:8px;font-size:12px;white-space:pre-wrap;margin:6px 0}
 .meta{color:#888;font-size:12px}
 .chips span{display:inline-block;background:#f0f3f6;border:1px solid #dde3ea;border-radius:14px;padding:3px 10px;font-size:12px;margin:3px 4px 0 0;cursor:pointer}
 .row{display:flex;gap:8px;margin-top:10px}
 textarea{flex:1;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:14px;resize:vertical}
 button{padding:10px 16px;border:0;border-radius:8px;background:#0a58ca;color:#fff;font-size:14px;cursor:pointer}
 button:disabled{background:#9bb8e6}
</style></head><body>
<h1>페르소나 개인화 테스트</h1>
<div class="sub" id="mode"></div>
<div class="wrap">
 <div class="card">
   <select id="sel" onchange="selPersona()"></select>
   <div class="pf" id="profile"></div>
   <div class="tags" id="tags"></div>
   <div class="pv">
     <h3>📋 개인화 미리보기 (결정적·로컬)</h3>
     <div id="bands"></div>
     <div class="dev" id="summary"></div>
     <div class="blk" id="block">질문을 보내면 결합될 ‘내 기록’ 블록이 표시됩니다.</div>
     <h3 style="margin-top:10px">🔐 옵션2: LLM에 들어갈 비식별 맥락</h3>
     <div class="blk" id="llmctx">밴드 라벨만(원시값·진단명 0). 서버 PERSONAL_SIGNAL_TO_LLM=on + 동의 시 본문 답변에 반영됩니다.</div>
   </div>
 </div>
 <div>
   <div id="chart" class="card" style="margin-bottom:10px"></div>
   <div id="profile" class="card" style="margin-bottom:10px"></div>
   <div id="log"></div>
   <div class="chips" id="chips"></div>
   <div class="row">
     <textarea id="q" rows="2" placeholder="질문 입력 (또는 위 예시 클릭)"></textarea>
     <button id="send" onclick="ask()">보내기</button>
   </div>
 </div>
</div>
<script>
let DATA={personas:[]}, cur=null, conv=crypto.randomUUID();
const LIVE = %LIVE%;
document.getElementById('mode').textContent = LIVE
  ? '백엔드 프록시 ON — 라이브 대화 + 개인화. (좌측은 결정적 미리보기)'
  : '미리보기 전용 모드 — 좌측에 페르소나별 개인화 블록 표시. (--rag-url 주면 라이브 대화)';
const log=document.getElementById('log');
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function inline(s){return s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');}
function md(src){const L=esc(src).split('\n');let o=[],il=false;
 for(const ln of L){const h=ln.match(/^\s*#{2,4}\s+(.*)$/);
  if(h){if(il){o.push('</ul>');il=false;}o.push('<h2>'+inline(h[1])+'</h2>');continue;}
  const li=ln.match(/^\s*[-*]\s+(.*)$/);
  if(li){if(!il){o.push('<ul>');il=true;}o.push('<li>'+inline(li[1])+'</li>');continue;}
  if(il){o.push('</ul>');il=false;} if(ln.trim()==='')continue; o.push('<p>'+inline(ln)+'</p>');}
 if(il)o.push('</ul>');return o.join('');}
function add(h){const d=document.createElement('div');d.innerHTML=h;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
const bcls={'안정':'b0','주의':'b1','경고':'b2'};
async function boot(){
  DATA=await (await fetch('/personas')).json();
  const sel=document.getElementById('sel');
  sel.innerHTML=DATA.personas.map(p=>`<option value="${p.id}">${p.emoji||''} ${p.name}</option>`).join('');
  selPersona();
}
function selPersona(){
  const id=document.getElementById('sel').value;
  cur=DATA.personas.find(p=>p.id===id);
  conv=crypto.randomUUID(); log.innerHTML='';
  document.getElementById('profile').textContent=cur.profile||'';
  document.getElementById('tags').innerHTML=(cur.tags||[]).map(t=>`<span>${t}</span>`).join('');
  document.getElementById('chips').innerHTML=(cur.sample_queries||[]).map(q=>`<span onclick="useChip(this)">${q}</span>`).join('');
  document.getElementById('block').textContent='질문을 보내면 결합될 ‘내 기록’ 블록이 표시됩니다.';
  refreshPreview('');
}
function useChip(el){document.getElementById('q').value=el.textContent;}
async function refreshPreview(query){
  const r=await (await fetch('/preview',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({persona_id:cur.id,query:query})})).json();
  document.getElementById('summary').textContent=r.summary||'';
  document.getElementById('bands').innerHTML=(r.findings||[]).map(f=>
    `<div class="band ${bcls[f.label_user]||''}">• ${f.signal}: <b>${f.label_user||'-'}</b> <span class="dev">(${f.clinical_label||''})</span></div>`).join('')
    || '<div class="dev">밴드 매칭 없음</div>';
  if(query){document.getElementById('block').textContent=r.safe_block||'(이 질문엔 결합 블록 없음 — 관련성 게이트)';}
  document.getElementById('llmctx').textContent = r.llm_context || '(이 질의엔 주입할 비식별 맥락 없음)';
  if(r.chart) drawChart(r.chart);
  if(r.profile) drawProfile(r.profile);
  return r;
}
function drawProfile(p){
  const host=document.getElementById('profile');
  const tag=(t,b)=>'<span style="display:inline-block;background:#f0f3f6;border:1px solid #dde3ea;border-radius:6px;padding:2px 8px;margin:2px 3px 0 0;font-size:12px">'+t+(b!==undefined?' <b>'+b+'</b>':'')+'</span>';
  const m=(p.measures||[]).map(x=>tag(x.label, x.value+(x.unit||''))).join('');
  const aq=p.air_quality? tag('실내 공기질', p.air_quality):'';
  const phr=(p.phr||[]).map(x=>'<div style="font-size:12px;margin:2px 0"><span class="dev">'+x.label+':</span> '+x.value+'</div>').join('') || '<div class="dev">기록 없음</div>';
  host.innerHTML='<div style="font-size:13px;font-weight:700;margin-bottom:6px">🗂️ 전체 입력 데이터 <span class="dev">(개발 점검용 · 측정 '+(p.readings||0)+'회)</span></div>'
    +'<div style="margin-bottom:8px">'+m+aq+'</div>'
    +'<div><div class="dev" style="margin-bottom:2px">PHR / 건강기록</div>'+phr+'</div>';
}
const ZC={'안정':['#2e7d32','#e7f3e8'],'주의':['#b06a00','#fdf1df'],'경고':['#c62828','#fbe9e9']};
function zcol(b){return ZC[b]||['#8a8a8a','#ececec'];}
function drawChart(spec){
  const host=document.getElementById('chart');
  if(!spec||!spec.series||!spec.series.length){host.innerHTML='<div class="dev">이 페르소나엔 그래프로 그릴 측정 신호가 없습니다.</div>';return;}
  const W=520,L=66,R=70,plotW=W-L-R,rowH=50,gap=12; let y=8,rows=[];
  for(const s of spec.series){
    const top=y,h=rowH,vmin=s.min,vmax=s.max;
    const vy=v=>top+h-3-((v-vmin)/(vmax-vmin))*(h-6);
    const n=s.points.length, px=i=> n<=1? L+plotW/2 : L+plotW*i/(n-1);
    let b='';
    for(const z of s.zones){const yA=vy(z.to),yB=vy(z.from);
      b+=`<rect x="${L}" y="${Math.min(yA,yB)}" width="${plotW}" height="${Math.abs(yB-yA)||1}" fill="${zcol(z.band)[1]}"/>`;}
    b+=`<line x1="${L}" y1="${top}" x2="${L}" y2="${top+h}" stroke="#d4dde7"/>`;
    b+=`<text x="0" y="${top+h/2-2}" font-size="12" font-weight="700">${s.label}</text>`;
    b+=`<text x="0" y="${top+h/2+12}" font-size="9" fill="#999">${s.unit||''}</text>`;
    if(s.second&&s.second.length>1){let d=s.second.map((p,i)=>`${i?'L':'M'}${px(i)},${vy(p.v)}`).join(' ');
      b+=`<path d="${d}" fill="none" stroke="#9bb8e6" stroke-width="1.2" stroke-dasharray="3 2"/>`;}
    if(s.second) s.second.forEach((p,i)=>{b+=`<circle cx="${px(i)}" cy="${vy(p.v)}" r="2.4" fill="#9bb8e6"/>`;});
    if(n>1){let d=s.points.map((p,i)=>`${i?'L':'M'}${px(i)},${vy(p.v)}`).join(' ');
      b+=`<path d="${d}" fill="none" stroke="#1f4e79" stroke-width="1.6"/>`;}
    s.points.forEach((p,i)=>{b+=`<circle cx="${px(i)}" cy="${vy(p.v)}" r="3.7" fill="${zcol(p.band)[0]}"><title>${p.t}: ${p.v}${s.unit} (${p.band||'-'})</title></circle>`;});
    const last=s.points[n-1],c=zcol(last.band);
    b+=`<rect x="${W-R+6}" y="${top+h/2-9}" width="56" height="18" rx="9" fill="${c[1]}" stroke="${c[0]}"/>`;
    b+=`<text x="${W-R+34}" y="${top+h/2+1}" font-size="11" fill="${c[0]}" text-anchor="middle" dominant-baseline="middle">${last.band||'-'}</text>`;
    rows.push('<g>'+b+'</g>'); y+=h+gap;
  }
  host.innerHTML=`<div style="font-size:13px;font-weight:700;margin-bottom:4px">📊 ${cur.emoji||''} ${cur.name} — 측정 그래프</div>`
    +`<svg viewBox="0 0 ${W} ${y}" width="100%" style="max-width:560px" font-family="inherit">${rows.join('')}</svg>`
    +`<div class="dev">점=측정값(색=밴드), 배경=참고 구간(안정/주의/경고), 점선=이완기·보조. 가로축=측정 시점.</div>`;
}
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q||!cur)return;
  const btn=document.getElementById('send');btn.disabled=true;
  add('<div class="u">🙋 '+esc(q)+'</div>');document.getElementById('q').value='';
  const pv=await refreshPreview(q);
  if(pv.safe_block){add('<div class="pblk">📋 결합된 내 기록(개인화 미리보기)\n'+esc(pv.safe_block)+'</div>');}
  if(!LIVE){btn.disabled=false;return;}
  const ans=add('<div class="a">…</div>');let text='',meta='';
  try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({persona_id:cur.id,query:q,conversation_id:conv})});
    const rd=res.body.getReader();const dec=new TextDecoder();let buf='';
    while(true){const{value,done}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});let i;
     while((i=buf.indexOf('\n\n'))>=0){const line=buf.slice(0,i);buf=buf.slice(i+2);
      const m=line.match(/^data: (.*)$/s);if(!m)continue;let ev;try{ev=JSON.parse(m[1]);}catch(e){continue;}
      if(ev.type==='GENERATION'){text+=(ev.text||'');ans.innerHTML='<div class="a">'+md(text)+'</div>';}
      else if(ev.type==='PROGRESS'){meta=ev.display_message||meta;}
      else if(ev.type==='ERROR'){text+='\n[오류] '+(ev.message||'');ans.innerHTML='<div class="a">'+md(text)+'</div>';}
      log.scrollTop=log.scrollHeight;}}
    if(meta)add('<div class="meta">'+esc(meta)+'</div>');
    if(!text)ans.innerHTML='<div class="a">(빈 응답 — 백엔드/검색 상태 확인)</div>';
  }catch(e){ans.innerHTML='<div class="a">[요청 실패] '+esc(''+e)+'</div>';}
  btn.disabled=false;
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask();}});
boot();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    rag_url = ""
    graph = "SUPERVISED_HYBRID_SEARCH"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = PAGE.replace("%LIVE%", "true" if self.rag_url else "false")
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path == "/personas":
            return self._send(200, json.dumps(load_personas(), ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_POST(self):
        if self.path == "/preview":
            req = self._read_body()
            p = _persona_by_id(load_personas(), req.get("persona_id"))
            if not p:
                return self._send(404, json.dumps({"error": "unknown persona"}))
            try:
                out = compute_preview(p, req.get("query") or "")
            except Exception as e:
                out = {"findings": [], "safe_block": "", "summary": f"미리보기 오류: {e}"}
            return self._send(200, json.dumps(out, ensure_ascii=False))
        if self.path == "/chat":
            return self._proxy_chat(self._read_body())
        self._send(404, json.dumps({"error": "not found"}))

    def _proxy_chat(self, req):
        if not self.rag_url:
            return self._send(200, 'data: {"type":"ERROR","message":"백엔드 미설정 — --rag-url 필요"}\n\n',
                              "text/event-stream; charset=utf-8")
        persona = _persona_by_id(load_personas(), req.get("persona_id"))
        if not persona:
            return self._send(404, json.dumps({"error": "unknown persona"}))
        payload = json.dumps({
            "query": req.get("query") or "",
            "conversation_strid": req.get("conversation_id") or "",
            "source_types": ["WEB"],
            "agent_input_field_to_value": build_agent_input(persona),
            "personal_consent": True,   # 데모: 동의 가정(옵션2 게이트 G2). 실제 플래그는 서버 env.
        }, ensure_ascii=False).encode("utf-8")
        url = f"{self.rag_url}/api/service/conversations/{self.graph}"
        r = urllib.request.Request(url, data=payload, headers=_headers(self.rag_url), method="POST")
        try:
            resp = urllib.request.urlopen(r, timeout=300)
        except urllib.error.HTTPError as e:
            return self._send(200, f'data: {{"type":"ERROR","message":"백엔드 {e.code}: 인증/요청 오류"}}\n\n',
                              "text/event-stream; charset=utf-8")
        except Exception as e:
            msg = json.dumps({"type": "ERROR", "message": f"연결 오류: {e}"}, ensure_ascii=False)
            return self._send(200, "data: " + msg + "\n\n", "text/event-stream; charset=utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                chunk = resp.read(512)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception:
            pass


def main():
    # Windows cp949 콘솔에서 한글·특수문자(—·) 출력 크래시 방지
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--rag-url", default=os.environ.get("PERSONA_RAG_URL", CLOUD_DEV_URL),
                    help="라이브 대화 대상 RAG 서버 (기본: 클라우드 dev)")
    ap.add_argument("--cloud", action="store_true", help="클라우드 dev RAG로 연결(기본값)")
    ap.add_argument("--preview", action="store_true", help="미리보기 전용 — 백엔드 미연결")
    ap.add_argument("--graph", default="SUPERVISED_HYBRID_SEARCH")
    args = ap.parse_args()

    # 우선순위: --preview(미연결) > --cloud > --rag-url(기본=클라우드 dev)
    if args.preview:
        rag_url = ""
    elif args.cloud:
        rag_url = CLOUD_DEV_URL
    else:
        rag_url = args.rag_url
    Handler.rag_url = (rag_url or "").rstrip("/")
    Handler.graph = args.graph

    data = load_personas()
    tok_note = None
    if ".run.app" in Handler.rag_url:  # 클라우드 대상이면 토큰 가용성 점검
        tok_note = "발급 OK" if get_id_token() else "실패(gcloud 로그인 필요)"
    print("=" * 60)
    print(" 페르소나 개인화 테스트 서버")
    print(f"  페르소나 : {len(data.get('personas', []))}개  ({PERSONAS_PATH.name})")
    print(f"  대상 RAG : {Handler.rag_url or '(없음 - 미리보기 전용, --preview)'}")
    if tok_note:
        print(f"  토큰     : {tok_note}")
    print(f"  브라우저 : http://localhost:{args.port}")
    print("  종료     : Ctrl+C")
    print("=" * 60)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
