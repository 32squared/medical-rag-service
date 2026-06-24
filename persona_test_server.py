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
        "checkup_chart": build_checkup_chart(persona),
        "prescriptions": __import__("persona_history").generate_prescriptions(persona),
        "profile": build_profile(persona),
        "clarifiers": __import__("followups").clarify(query or "", personal_findings=raw),
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
    """페르소나 → 신호별 일일 시계열 차트 스펙(원시값은 점 좌표로만, 라벨=밴드 색)."""
    from persona_history import generate_vitals_series, window_days
    vitals = generate_vitals_series(persona)
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
    return {"series": series, "window_days": window_days(persona)}


# 검진 추이용 추가 구간(연 1회 × 10년)
_GLU_ZONES = [("안정", 70, 100), ("주의", 100, 126), ("경고", 126, 160)]
_HBA1C_ZONES = [("안정", 4.5, 5.7), ("주의", 5.7, 6.5), ("경고", 6.5, 9)]


def _zfmt(zt):
    return [{"band": z[0], "from": z[1], "to": z[2]} for z in zt]


def _mk_series(label, unit, vmin, vmax, zones_tuples, points):
    return {"signal": label, "label": label, "unit": unit, "min": vmin, "max": vmax,
            "zones": _zfmt(zones_tuples), "points": points, "second": []}


def build_checkup_chart(persona: dict) -> dict:
    """건강검진 10년치 → 지표별 연도 추이 차트(혈압·공복혈당·콜레스테롤·BMI·당화혈색소)."""
    import vital_rules as vr
    from persona_history import generate_checkups
    rows = generate_checkups(persona)
    if not rows:
        return {"series": [], "years": 0}

    def cls(sig, val):
        b = vr.lookup_band(sig, val)
        return b["label_user"] if b["match"] == "ok" else None

    def cls_bp(r):
        b = vr.lookup_band("blood_pressure", {"systolic": r["수축기"], "diastolic": r["이완기"]})
        return b["label_user"] if b["match"] == "ok" else None

    yrs = [str(r["year"]) for r in rows]
    series = [
        _mk_series("혈압(수축기)", "mmHg", 90, 190, _GAUGE["blood_pressure"]["zones"],
                   [{"t": yrs[i], "v": r["수축기"], "band": cls_bp(r)} for i, r in enumerate(rows)]),
        _mk_series("공복혈당", "mg/dL", 70, 160, _GLU_ZONES,
                   [{"t": yrs[i], "v": r["공복혈당"], "band": cls("fasting_glucose", r["공복혈당"])} for i, r in enumerate(rows)]),
        _mk_series("총콜레스테롤", "mg/dL", 120, 280, [],
                   [{"t": yrs[i], "v": r["총콜레스테롤"], "band": None} for i, r in enumerate(rows)]),
        _mk_series("체질량지수", "", 15, 40, _GAUGE["bmi"]["zones"],
                   [{"t": yrs[i], "v": r["BMI"], "band": cls("bmi", r["BMI"])} for i, r in enumerate(rows)]),
    ]
    if "당화혈색소" in rows[0]:
        series.append(_mk_series("당화혈색소", "%", 4.5, 9, _HBA1C_ZONES,
                      [{"t": yrs[i], "v": r["당화혈색소"], "band": cls("hba1c", r["당화혈색소"])} for i, r in enumerate(rows)]))
    return {"series": series, "years": len(rows)}


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


# ── 클라우드 토큰(선택) — Cloud Run 메타데이터 서버 또는 로컬 gcloud ──
_token = {}  # audience → (token, ts)


def get_id_token(audience=None, force=False):
    """RAG(IAM 보호) 호출용 identity 토큰.

    Cloud Run 런타임(K_SERVICE)에선 메타데이터 서버로 audience=RAG URL 토큰을 받고
    (컨테이너엔 gcloud 없음), 로컬에선 gcloud print-identity-token 폴백.
    """
    key = audience or "_"
    now = time.time()
    cached = _token.get(key)
    if not force and cached and now - cached[1] < 2400:
        return cached[0]
    tok = None
    if os.environ.get("K_SERVICE"):  # Cloud Run 런타임 → 서비스계정 토큰
        try:
            aud = quote(audience or "", safe="")
            req = urllib.request.Request(
                "http://metadata.google.internal/computeMetadata/v1/instance/"
                "service-accounts/default/identity?audience=" + aud,
                headers={"Metadata-Flavor": "Google"})
            tok = urllib.request.urlopen(req, timeout=5).read().decode().strip() or None
        except Exception as e:
            sys.stderr.write(f"[token:metadata] {e}\n")
    if not tok:
        try:
            out = subprocess.run("gcloud auth print-identity-token", shell=True,
                                 capture_output=True, text=True, timeout=30)
            tok = (out.stdout or "").strip() or None
        except Exception as e:
            sys.stderr.write(f"[token:gcloud] {e}\n")
    if tok:
        _token[key] = (tok, now)
    return tok


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
    if ".run.app" in rag_url:  # 클라우드 대상이면 IAM 토큰(audience=RAG URL)
        tok = get_id_token(audience=rag_url)
        if tok:
            h["Authorization"] = "Bearer " + tok
    return h


def _rag_persist(path: str, payload: dict, timeout: int = 8):
    """뷰어→RAG 비식별 영속 호출(SA 토큰). 실패는 비치명(None) — 데모는 계속 동작."""
    try:
        url = Handler.rag_url + path
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        for k, v in _headers(Handler.rag_url).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


# ── HTML ─────────────────────────────────────────────────────
PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>페르소나 개인화 테스트</title>
<style>
 *{box-sizing:border-box}
 body{font-family:system-ui,'Malgun Gothic',sans-serif;margin:0;color:#1c1c1c;background:#f7f8fa}
 .top{padding:10px 16px;border-bottom:1px solid #e5e9ee;background:#fff;position:sticky;top:0;z-index:20}
 .top h1{font-size:16px;margin:0;display:inline-block} .sub{color:#888;font-size:12px;margin-left:10px}
 .app{display:grid;grid-template-columns:260px minmax(0,1fr) minmax(0,1.05fr);gap:12px;padding:12px;align-items:start}
 .col{min-width:0} .colhdr{font-size:12px;font-weight:700;color:#1f4e79;margin:0 2px 6px}
 .card{background:#fff;border:1px solid #e2e6ea;border-radius:10px;padding:12px;margin-bottom:10px}
 .card h3{font-size:12px;color:#1f4e79;margin:0 0 5px}
 select{width:100%;padding:8px;border:1px solid #ccc;border-radius:8px;font-size:14px}
 .pf{font-size:13px;color:#444;margin:8px 0;line-height:1.5}
 .tags span{display:inline-block;background:#eef3f8;color:#3a5a78;border-radius:10px;padding:1px 8px;font-size:11px;margin:2px 3px 0 0}
 .band{font-size:12px;margin:2px 0}
 .b0{color:#2e7d32}.b1{color:#b06a00}.b2{color:#c62828;font-weight:600}
 .blk{background:#f6f8fb;border:1px solid #e0e6ee;border-radius:8px;padding:8px;font-size:12px;white-space:pre-wrap;margin-top:4px}
 .dev{color:#aaa;font-size:11px}
 .stack{max-height:calc(100vh - 96px);overflow:auto;padding-right:4px}
 #log{min-height:300px;max-height:calc(100vh - 210px);overflow:auto;line-height:1.5}
 .u{color:#0a58ca;font-weight:600;margin-top:10px;white-space:pre-wrap}
 .a{color:#111;margin:4px 0 10px} .a h2{font-size:15px;margin:12px 0 6px;border-bottom:1px solid #eee}
 .a p{margin:4px 0} .a ul{margin:4px 0 8px;padding-left:20px} .a strong{font-weight:700}
 .cite{color:#0a58ca;cursor:pointer;font-weight:600;border-bottom:1px dotted #0a58ca;padding:0 1px}
 .meta{color:#888;font-size:12px;margin:4px 0}
 .chips span{display:inline-block;background:#f0f3f6;border:1px solid #dde3ea;border-radius:14px;padding:3px 10px;font-size:12px;margin:3px 4px 0 0;cursor:pointer}
 #followups{margin:8px 0 2px}
 .fulabel{color:#888;font-size:11px;margin:0 0 4px}
 .fu{display:inline-block;background:#fff;border:1px solid #b9c9e8;color:#0a58ca;border-radius:16px;padding:6px 13px;font-size:12.5px;margin:0 6px 6px 0;cursor:pointer;text-align:left}
 .fu:hover{background:#eef3fb;border-color:#0a58ca}
 .fu.on{background:#0a58ca;color:#fff;border-color:#0a58ca}
 .row{display:flex;gap:8px;margin-top:10px}
 textarea{flex:1;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:14px;resize:vertical}
 button{padding:10px 16px;border:0;border-radius:8px;background:#0a58ca;color:#fff;font-size:14px;cursor:pointer}
 button:disabled{background:#9bb8e6}
 #pop{position:fixed;z-index:50;max-width:330px;background:#fff;border:1px solid #cfd6de;border-radius:8px;padding:10px 12px;box-shadow:0 6px 22px rgba(0,0,0,.16);font-size:12px;display:none}
 #pop a{color:#0a58ca;word-break:break-all}
 @media(max-width:1100px){.app{grid-template-columns:1fr}.stack,#log{max-height:none}}
</style></head><body>
<div class="top"><h1>페르소나 개인화 테스트</h1><span class="sub" id="mode"></span></div>
<div style="background:#FAEEDA;color:#854F0B;border:1px solid #EF9F27;border-radius:8px;padding:6px 11px;margin:0 0 10px;font-size:12px;line-height:1.5">⚠️ <b>테스트용 프로토타입</b> · 모든 페르소나는 <b>합성(가짜) 데이터</b>입니다 · 의료 자문이 아니며, 실제 증상은 의료진과 상담하세요.</div>
<div class="app">
 <div class="col">
   <div class="colhdr">① 페르소나 요약·선택</div>
   <div class="card">
     <select id="sel" onchange="selPersona()"></select>
     <div class="pf" id="pfdesc"></div>
     <div class="tags" id="tags"></div>
     <div class="dev" id="expected" style="margin-top:8px"></div>
   </div>
 </div>
 <div class="col">
   <div class="colhdr">② 개인화 정보</div>
   <div class="stack">
     <div class="card"><h3>밴드 / 추세</h3><div id="bands"></div><div class="dev" id="summary"></div></div>
     <div class="card"><h3>📋 결합 블록 (답변에 붙는 ‘내 기록’)</h3><div class="blk" id="block">질문을 보내면 결합될 블록이 표시됩니다.</div></div>
     <div class="card"><h3>🔐 LLM 비식별 맥락 (옵션2)</h3><div class="blk" id="llmctx">밴드 라벨만(원시값·진단명 0). 서버 PERSONAL_SIGNAL_TO_LLM=on + 동의 시 답변 본문 반영.</div></div>
     <div id="chart" class="card"></div>
     <div id="checkup" class="card"></div>
     <div id="rx" class="card"></div>
     <div id="profile" class="card"></div>
   </div>
 </div>
 <div class="col">
   <div class="colhdr">③ 대화</div>
   <div class="card">
     <div id="log"></div>
     <div id="followups"></div>
     <div class="chips" id="chips"></div>
     <div class="row">
       <textarea id="q" rows="2" placeholder="질문 입력 (또는 추천 질문·예시 클릭)"></textarea>
       <button id="send" onclick="ask()">보내기</button>
     </div>
   </div>
 </div>
</div>
<div id="pop"></div>
<script>
let DATA={personas:[]}, cur=null, conv=crypto.randomUUID(), citeSources=[];
const LIVE = %LIVE%;
document.getElementById('mode').textContent = LIVE
  ? '라이브 대화 ON · 3분할(① 페르소나 / ② 개인화 / ③ 대화) · 답변의 인용 [n] 클릭=출처'
  : '미리보기 전용 · 3분할 뷰 · 라이브 대화는 서버 --rag-url 필요';
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
  conv=crypto.randomUUID(); log.innerHTML=''; citeSources=[]; iv=null;
  document.getElementById('followups').innerHTML='';
  document.getElementById('pfdesc').textContent=cur.profile||'';
  document.getElementById('tags').innerHTML=(cur.tags||[]).map(t=>`<span>${t}</span>`).join('');
  document.getElementById('expected').textContent=cur.expected_label?('예상: '+cur.expected_label):'';
  document.getElementById('chips').innerHTML=(cur.sample_queries||[]).map(q=>`<span onclick="useChip(this)">${q}</span>`).join('');
  document.getElementById('block').textContent='질문을 보내면 결합될 블록이 표시됩니다.';
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
  if(r.chart) drawChart('chart', r.chart, '📊 '+(cur.emoji||'')+' '+cur.name+' — 바이탈 추이', vitalsCaption(r.chart));
  if(r.checkup_chart) drawChart('checkup', r.checkup_chart, '🩺 건강검진 추이 (연 1회 × '+(r.checkup_chart.years||0)+'년)', '가로축=연도. 점=검진값(색=밴드), 배경=참고 구간.');
  if(r.prescriptions) drawRx(r.prescriptions);
  if(r.profile) drawProfile(r.profile);
  return r;
}
// 답변 먼저 → 그 답변을 바탕으로 되묻기(문진). Claude Code가 일단 작업하고 필요할 때 되묻듯.
// 순차(한 번에 한 질문) → 선택 → 다음 질문 → 다 모이면 그 정보로 답변을 좁혀 재안내.
let iv=null;
function offerInterview(query, c){
  if(!c||!c.questions||!c.questions.length) return;
  iv={query:query, questions:c.questions, idx:0, answers:[], last:null};
  add('<div class="meta">🩺 더 정확히 좁혀 드릴까요? 아래에 답해 주시면 위 답변을 상황에 맞게 다시 안내드려요 — 또는 ‘괜찮아요’</div>');
  postQuestion();
}
function postQuestion(){
  const qq=iv.questions[iv.idx];
  const opts=qq.options.map(o=>'<button class="fu" data-v="'+esc(o)+'" onclick="answerIv(this)">'+esc(o)+'</button>').join('');
  iv.last=add('<div class="a"><b>('+(iv.idx+1)+'/'+iv.questions.length+')</b> '+esc(qq.q)
    +'<div style="margin-top:6px">'+opts+'<button class="fu" style="color:#888;border-color:#d2d2d2" onclick="finishIv()">괜찮아요</button></div></div>');
}
function answerIv(el){
  if(!iv) return;
  if(iv.last) iv.last.querySelectorAll('button').forEach(b=>{b.disabled=true;b.style.opacity=.5;});
  el.style.opacity=1; el.classList.add('on');
  iv.answers.push(el.dataset.v);
  add('<div class="u">→ '+esc(el.dataset.v)+'</div>');
  iv.idx++;
  if(iv.idx<iv.questions.length) postQuestion(); else finishIv();
}
function finishIv(){
  if(!iv) return;
  if(iv.last) iv.last.querySelectorAll('button').forEach(b=>{b.disabled=true;});
  const q0=iv.query, ans=iv.answers; iv=null;
  if(!ans.length){add('<div class="meta">알겠습니다 — 더 궁금한 점 있으면 말씀해 주세요.</div>');return;}
  const enriched=q0+' / 문진: '+ans.join(', ');
  add('<div class="meta">↳ 받은 정보로 다시 안내드릴게요.</div>');
  refreshPreview(enriched); sendToRag(enriched);   // 정밀 답변(재문진 없음 — clarifiers 미전달)
}
function sendToRag(q, clarifiers){
  const btn=document.getElementById('send'); btn.disabled=true;
  if(!LIVE){add('<div class="meta">(미리보기 전용 — 라이브 답변은 서버 --rag-url 필요)</div>');btn.disabled=false;
    if(clarifiers) offerInterview(q, clarifiers); return;}
  citeSources=[];
  const ans=add('<div class="a">…</div>'); let text='',meta='';
  // 후처리(생성 직후~STOP) 침묵 구간을 설명하는 상태줄 — 토큰 흐름 디바운스로 단계 전환
  const st=add('<div class="meta">🔎 검색·근거 검증 중…</div>'); let gtimer=null;
  const setSt=h=>{st.innerHTML='<div class="meta">'+h+'</div>';log.scrollTop=log.scrollHeight;};
  const clearSt=()=>{if(gtimer)clearTimeout(gtimer);if(st&&st.parentNode)st.remove();};
  (async()=>{
   try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({persona_id:cur.id,query:q,conversation_id:conv})});
    const rd=res.body.getReader();const dec=new TextDecoder();let buf='';let stopped=false;let pinj=null;let hoff=null;
    while(true){const{value,done}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});let i;
     while((i=buf.indexOf('\n\n'))>=0){const line=buf.slice(0,i);buf=buf.slice(i+2);
      const m=line.match(/^data: (.*)$/s);if(!m)continue;let ev;try{ev=JSON.parse(m[1]);}catch(e){continue;}
      if(ev.type==='INFO'&&ev.data&&ev.data.search_results){citeSources=ev.data.search_results;}
      else if(ev.type==='GENERATION'){text+=(ev.text||'');ans.innerHTML='<div class="a">'+linkCites(md(text))+'</div>';
        setSt('✍️ 답변 생성 중…');                            // 토큰 오는 동안
        if(gtimer)clearTimeout(gtimer);
        gtimer=setTimeout(()=>setSt('🔍 마무리 점검 중 — 근거·인용·안전 검증, 기록 저장…'),1500);}  // 멈추면 후처리로
      else if(ev.type==='PROGRESS'){meta=ev.display_message||meta;}
      else if(ev.type==='STOP'){stopped=true;                  // STOP 즉시 마무리(연결 종료 대기 안 함)
        if(ev.personal_injected&&ev.personal_injected.length)pinj=ev.personal_injected;  // 방향2 주입 밴드
        if(ev.handoff)hoff=ev.handoff;}                        // 핸드오프(코칭 버튼) 메타
      else if(ev.type==='ERROR'){text+='\n[오류] '+(ev.message||'');ans.innerHTML='<div class="a">'+linkCites(md(text))+'</div>';}
      log.scrollTop=log.scrollHeight;}
     if(stopped){try{await rd.cancel();}catch(e){} break;}}    // STOP 받으면 읽기 중단
    clearSt();                                                // STOP/스트림 끝 → 상태줄 제거
    if(pinj)add('<div style="margin:4px 0;padding:5px 9px;background:#eef4ff;border:1px solid #b9d0f5;'
      +'border-radius:7px;font-size:12px;color:#1f4e79">🔐 이 답변에 <b>개인맥락(방향2)</b>이 반영됨 — 주입 밴드: '
      +'<b>'+esc(pinj.join(', '))+'</b> <span class="dev">(원시 수치·진단명 0, 밴드 라벨만)</span></div>');
    if(hoff&&hoff.show){const sft=hoff.copy==='soft';   // 핸드오프 코칭 버튼(P1 — 클릭 시 트랙 선택 stub)
      add('<div style="margin:7px 0"><button onclick="alert(\'트랙 선택(P2 예정): 🥗 식단 · 🏃 운동 · 😴 생활습관\')" '
       +'style="background:'+(sft?'#eaf6f1':'#0E8A6B')+';color:'+(sft?'#0b5f4a':'#fff')+';border:1px solid '
       +(sft?'#bfe3d6':'#0E8A6B')+';border-radius:10px;padding:9px 15px;font-size:13px;font-weight:600;cursor:pointer">'
       +(sft?'🌿 ':'💪 ')+esc(hoff.label||'실천 코칭 받기')+'</button>'
       +(hoff.banner?' <span class="dev">· 진료와 병행 권장</span>':'')+'</div>');}
    if(hoff&&hoff.referral==='emergency')add('<div style="margin:4px 0;color:#a32d2d;font-size:12px">🚑 응급 시 즉시 119·응급실</div>');
    let mm=meta; if(citeSources.length) mm+=(mm?' · ':'')+'인용 '+citeSources.length+'개 — [n] 클릭=출처';
    if(mm)add('<div class="meta">'+esc(mm)+'</div>');
    if(!text)ans.innerHTML='<div class="a">(빈 응답 — 백엔드/검색 상태 확인)</div>';
    if(clarifiers) offerInterview(q, clarifiers);   // ← 답변이 끝난 뒤 되묻기(문진) 제안
   }catch(e){clearSt();ans.innerHTML='<div class="a">[요청 실패] '+esc(''+e)+'</div>';}
   btn.disabled=false;
  })();
}
function vitalsCaption(c){return '가로축=측정 시점(최근 '+(c.window_days||0)+'일, 매일 측정). 점=측정값(색=밴드), 배경=참고 구간, 파란 점=이완기.';}
function drawRx(list){
  const host=document.getElementById('rx');
  if(!list||!list.length){host.innerHTML='<div class="dev">처방·진료 이력 없음</div>';return;}
  const rows=list.slice().reverse().map(v=>{
    const drug=v.drug?(' · 처방 '+v.drug+' '+v.days+'일분'):'';
    return '<div style="font-size:12px;margin:3px 0;display:flex;gap:8px"><span class="dev" style="min-width:80px">'+v.date+'</span><span><b>'+v.dept+'</b> · '+v.reason+drug+'</span></div>';
  }).join('');
  host.innerHTML='<div style="font-size:13px;font-weight:700;margin-bottom:6px">💊 처방·진료 이력 <span class="dev">(최근 5년 · '+list.length+'건, 최신순)</span></div>'+rows;
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
function drawChart(hostId, spec, title, sub){
  const host=document.getElementById(hostId);
  if(!spec||!spec.series||!spec.series.length){host.innerHTML='<div class="dev">그릴 데이터가 없습니다.</div>';return;}
  const W=520,L=66,R=70,plotW=W-L-R,rowH=46,gap=12; let y=8,rows=[];
  for(const s of spec.series){
    const top=y,h=rowH,vmin=s.min,vmax=s.max;
    const vy=v=>top+h-3-((v-vmin)/(vmax-vmin))*(h-6);
    const n=s.points.length, px=i=> n<=1? L+plotW/2 : L+plotW*i/(n-1);
    const pr = n>40?1.5:(n>12?2.4:3.6);
    let b='';
    for(const z of s.zones){const yA=vy(z.to),yB=vy(z.from);
      b+=`<rect x="${L}" y="${Math.min(yA,yB)}" width="${plotW}" height="${Math.abs(yB-yA)||1}" fill="${zcol(z.band)[1]}"/>`;}
    b+=`<line x1="${L}" y1="${top}" x2="${L}" y2="${top+h}" stroke="#d4dde7"/>`;
    b+=`<text x="0" y="${top+h/2-2}" font-size="11.5" font-weight="700">${s.label}</text>`;
    b+=`<text x="0" y="${top+h/2+12}" font-size="9" fill="#999">${s.unit||''}</text>`;
    if(s.second&&s.second.length>1){let d=s.second.map((p,i)=>`${i?'L':'M'}${px(i)},${vy(p.v)}`).join(' ');
      b+=`<path d="${d}" fill="none" stroke="#9bb8e6" stroke-width="1" stroke-dasharray="3 2"/>`;}
    else if(s.second) s.second.forEach((p,i)=>{b+=`<circle cx="${px(i)}" cy="${vy(p.v)}" r="2.4" fill="#9bb8e6"/>`;});
    if(n>1){let d=s.points.map((p,i)=>`${i?'L':'M'}${px(i)},${vy(p.v)}`).join(' ');
      b+=`<path d="${d}" fill="none" stroke="#1f4e79" stroke-width="1.4"/>`;}
    s.points.forEach((p,i)=>{b+=`<circle cx="${px(i)}" cy="${vy(p.v)}" r="${pr}" fill="${zcol(p.band)[0]}"><title>${p.t}: ${p.v}${s.unit} (${p.band||'무분류'})</title></circle>`;});
    const last=s.points[n-1],c=zcol(last.band);
    b+=`<rect x="${W-R+6}" y="${top+h/2-9}" width="56" height="18" rx="9" fill="${c[1]}" stroke="${c[0]}"/>`;
    b+=`<text x="${W-R+34}" y="${top+h/2+1}" font-size="11" fill="${c[0]}" text-anchor="middle" dominant-baseline="middle">${last.band||'-'}</text>`;
    rows.push('<g>'+b+'</g>'); y+=h+gap;
  }
  host.innerHTML=`<div style="font-size:13px;font-weight:700;margin-bottom:4px">${title}</div>`
    +`<svg viewBox="0 0 ${W} ${y}" width="100%" style="max-width:560px" font-family="inherit">${rows.join('')}</svg>`
    +`<div class="dev">${sub||''}</div>`;
}
function linkCites(html){return html.replace(/\[(\d+)\]/g,(m,n)=>'<a class="cite" onclick="showCite(event,'+n+')">['+n+']</a>');}
const SRC_URL={'질병관리청 국가건강정보포털':'https://health.kdca.go.kr','질병관리청 감염병포털':'https://www.kdca.go.kr','질병관리청 예방접종도우미':'https://nip.kdca.go.kr','식약처 의약품안전나라':'https://nedrug.mfds.go.kr','식약처 DUR':'https://nedrug.mfds.go.kr','식약처 e약은요':'https://nedrug.mfds.go.kr','응급의료포털 E-Gen':'https://www.e-gen.or.kr','국가법령정보센터':'https://www.law.go.kr'};
function showCite(ev,n){
  ev.stopPropagation();
  const s=citeSources[n-1],pop=document.getElementById('pop');
  if(!s){pop.innerHTML='<div class="dev">['+n+'] 출처 정보가 없습니다.</div>';}
  else{
    const url=s.url||SRC_URL[s.source]||'';
    const exact=!!s.url, host=(url&&url.split('/')[2])||url;
    const link = url
      ? '<a href="'+url+'" target="_blank" rel="noopener">'+esc(host)+' ↗</a>'+(exact?'':' <span class="dev">(출처 기관 사이트)</span>')
      : '<span class="dev">공개 원문 링크 없음 (내부·시드 콘텐츠)</span>';
    pop.innerHTML='<div style="font-weight:700;margin-bottom:3px">['+n+'] '+esc(s.source||'출처')+'</div>'
      +(s.title?'<div style="color:#333;margin-bottom:3px">'+esc(s.title)+'</div>':'')
      +(s.snippet?'<div style="font-size:11px;color:#777;margin-bottom:5px">'+esc((s.snippet||'').slice(0,200))+'</div>':'')
      +link;}
  pop.style.display='block';
  const w=Math.min(330,window.innerWidth-20);
  pop.style.left=Math.max(8,Math.min(ev.clientX,window.innerWidth-w-12))+'px';
  pop.style.top=(ev.clientY+14)+'px';
}
document.addEventListener('click',e=>{if(!e.target.closest('#pop')&&!e.target.classList.contains('cite'))document.getElementById('pop').style.display='none';});
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q||!cur||iv)return;
  document.getElementById('q').value='';
  add('<div class="u">🙋 '+esc(q)+'</div>');
  const pv=await refreshPreview(q);     // 개인화 정보 갱신
  // ① 일단 답변을 먼저 준다 → ② 답변이 끝나면 그 답변을 바탕으로 되묻기(문진) 제안.
  // 이미 문진 답을 실은 질의(/ 문진:)면 재문진 없이 정밀 답변만.
  const clar = /\/ 문진:/.test(q) ? null : (pv && pv.clarifiers);
  sendToRag(q, clar);
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask();}});
boot();
</script></body></html>"""


# ── Warm Light 앱 (확정 디자인 적용 — /app) ─────────────────────────────────
APP_PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont/dist/tabler-icons.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}
.ti{font-family:'tabler-icons'!important;font-style:normal}
body{font-family:'Pretendard',sans-serif;background:#EEEBE3;color:#232220}
.app{max-width:440px;margin:0 auto;min-height:100vh;background:#F6F4EF;display:flex;flex-direction:column;position:relative}
.hd{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid rgba(0,0,0,.06);background:#F6F4EFdd;position:sticky;top:0;z-index:5;backdrop-filter:blur(6px)}
.lg{width:30px;height:30px;border-radius:50%;background:#E1F5EE;color:#0E8A6B;display:flex;align-items:center;justify-content:center;font-size:17px}
.hd .nm{font-size:15.5px;font-weight:600;letter-spacing:-.3px;flex:1}
.hd select{font-size:12px;color:#5F5E58;border:1px solid rgba(0,0,0,.1);border-radius:8px;padding:5px 7px;background:#fff;max-width:140px}
.chat{flex:1;overflow-y:auto;padding:18px 16px 8px;display:flex;flex-direction:column;gap:12px}
.bu{align-self:flex-end;max-width:82%;background:#0E8A6B;color:#fff;border-radius:16px;border-top-right-radius:5px;padding:10px 14px;font-size:14.5px;line-height:1.5;letter-spacing:-.2px}
.ba{align-self:flex-start;max-width:88%;display:flex;gap:9px}
.av{width:28px;height:28px;border-radius:50%;flex:none;background:#0E8A6B;color:#fff;display:flex;align-items:center;justify-content:center;font-size:15px}
.bx{background:#fff;border:1px solid rgba(0,0,0,.07);border-radius:16px;border-top-left-radius:5px;padding:12px 14px;font-size:14.5px;line-height:1.62;color:#232220;letter-spacing:-.2px;box-shadow:0 4px 14px rgba(0,0,0,.04)}
.bx b{font-weight:600}
.cite{font-size:11px;background:rgba(14,138,107,.1);color:#0B5F4A;border-radius:4px;padding:1px 5px;font-weight:600}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;background:rgba(14,138,107,.1);color:#0B5F4A;border-radius:20px;padding:5px 11px;margin-top:7px}
.meta{font-size:11.5px;color:#9A988F;margin:2px 0 0 37px}
.ho{margin:2px 0 4px 37px;display:flex;flex-direction:column;gap:7px;align-items:flex-start}
.hob{display:inline-flex;align-items:center;gap:7px;border-radius:11px;padding:10px 15px;font-size:13.5px;font-weight:600;cursor:pointer;border:none}
.hob.full{background:#0E8A6B;color:#fff}
.hob.soft{background:#EAF6F1;color:#0B5F4A;border:1px solid #bfe3d6}
.emg{font-size:12.5px;color:#C0392B;font-weight:500;margin:2px 0 0 37px}
.card{background:#fff;border:1px solid rgba(0,0,0,.07);border-radius:18px;padding:16px;box-shadow:0 5px 18px rgba(0,0,0,.05);align-self:stretch}
.tlab{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#0E8A6B;margin-bottom:9px;display:flex;align-items:center;gap:6px}
.trk{display:flex;gap:8px;flex-wrap:wrap}
.tk{border:1px solid rgba(0,0,0,.1);border-radius:12px;padding:11px 14px;font-size:13.5px;font-weight:600;cursor:pointer;background:#fff;display:flex;align-items:center;gap:7px}
.tk.on{border-color:#0E8A6B;color:#0E8A6B}.tk.dim{opacity:.45}
.tk i{font-size:17px;color:#0E8A6B}
.qh{font-size:16px;font-weight:600;letter-spacing:-.3px;margin-bottom:12px}
.opt{display:block;width:100%;text-align:left;border:1px solid rgba(0,0,0,.1);border-radius:11px;padding:12px 14px;font-size:14px;margin:7px 0;background:#fff;cursor:pointer;color:#232220}
.opt:hover{border-color:#0E8A6B}
.prog{height:6px;background:rgba(0,0,0,.07);border-radius:4px;overflow:hidden;margin-bottom:12px}
.prog>div{height:100%;background:#0E8A6B;border-radius:4px;transition:width .25s}
.ph{font-size:16.5px;font-weight:600;letter-spacing:-.3px}
.psub{font-size:12.5px;color:#8A887F;margin:2px 0 10px}
.it{display:flex;align-items:center;gap:10px;font-size:14.5px;padding:9px 0;border-bottom:1px solid #F2F0E9}
.it:last-child{border-bottom:none}.it i{font-size:19px;color:#C2C0B6}
.icite{font-size:10.5px;color:#9A988F;margin:6px 0 0}
.ban{display:flex;gap:8px;align-items:flex-start;background:rgba(224,162,62,.1);color:#B5721A;border-radius:11px;padding:11px 13px;font-size:12.5px;line-height:1.5;margin-top:12px}
.ban i{font-size:16px;flex:none}
.inbar{position:sticky;bottom:0;display:flex;gap:9px;align-items:center;padding:12px 16px;background:#F6F4EF;border-top:1px solid rgba(0,0,0,.06)}
.inbar input{flex:1;border:1px solid rgba(0,0,0,.1);border-radius:18px;padding:11px 15px;font-size:14px;background:#fff;outline:none;font-family:inherit}
.inbar input:focus{border-color:#0E8A6B}
.snd{width:40px;height:40px;border-radius:50%;background:#0E8A6B;color:#fff;border:none;display:flex;align-items:center;justify-content:center;font-size:19px;cursor:pointer;flex:none}
.note{font-size:11px;color:#B0AEA3;text-align:center;padding:5px}
.pchip{padding:6px 11px;border-radius:16px;background:#F2F0E9;font-size:13px;cursor:pointer;border:1px solid transparent;user-select:none}
.pchip.on{background:rgba(14,138,107,.12);color:#0B5F4A;border-color:rgba(14,138,107,.3);font-weight:600}
.icobtn{width:34px;height:34px;border-radius:10px;border:1px solid rgba(0,0,0,.1);background:#fff;cursor:pointer;color:#0E8A6B;display:flex;align-items:center;justify-content:center;flex:none}
</style></head>
<body><div class="app">
<div class="hd"><div class="lg"><i class="ti ti-heart"></i></div><span class="nm">마이헬스케어</span>
  <select id="persona"></select><button class="icobtn" onclick="openProfile()" title="내 정보"><i class="ti ti-user-cog"></i></button></div>
<div class="chat" id="chat"></div>
<div class="note">합성 데이터 · 의료 자문 아님 · 진단·처방 0</div>
<div class="inbar"><input id="q" placeholder="건강에 대해 무엇이든 물어보세요" autocomplete="off">
  <button class="snd" onclick="ask()"><i class="ti ti-arrow-up"></i></button></div>
</div>
<script>
var chat=document.getElementById('chat'),qi=document.getElementById('q'),psel=document.getElementById('persona');
var _track='diet';
var INTAKE_BY_TRACK={
 diet:[{id:'eatout',q:'평소 외식·배달 빈도는?',o:['거의 매일','주 2~3회','드뭄']},
       {id:'salty',q:'짠 음식·국물 선호도는?',o:['강함','보통','약함']},
       {id:'period',q:'목표 기간은?',o:['2주','1개월','3개월+']}],
 exercise:[{id:'now',q:'지금 운동 습관은?',o:['거의 안 함','가끔','주 3회+']},
       {id:'activity',q:'주로 가능한 활동은?',o:['걷기','홈트','헬스·유산소']},
       {id:'goal',q:'목표는?',o:['활동량 늘리기','체중','체력']}],
 habit:[{id:'focus',q:'가장 개선하고 싶은 것은?',o:['수면','스트레스','금연·절주']},
       {id:'reg',q:'요즘 생활 리듬은?',o:['불규칙','보통','규칙적']},
       {id:'period',q:'목표 기간은?',o:['2주','1개월']}]};
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function md(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n/g,'<br>');}
function cites(s){return md(s).replace(/\[(\d+)\]/g,'<span class="cite">$1</span>');}
function el(h){var d=document.createElement('div');d.innerHTML=h;chat.appendChild(d.firstChild);chat.scrollTop=chat.scrollHeight;return chat.lastChild;}
async function boot(){try{var p=await (await fetch('/personas')).json();var arr=p.personas||p||[];
  psel.innerHTML=arr.map(x=>'<option value="'+x.id+'">'+esc(x.name||x.id)+'</option>').join('');
  var hi=arr.findIndex(x=>/혈압|고혈압/.test((x.name||'')+(x.tagline||'')));if(hi>0)psel.selectedIndex=hi;}catch(e){}
  psel.onchange=afterPersona;
  if(localStorage.getItem('mhc_onboarded')){afterPersona();}else{showOnboarding();}}
function consentRow(id,label,tag,checked){
  var tc=tag==='필수'?'rgba(192,57,43,.1);color:#C0392B':'rgba(0,0,0,.06);color:#8A887F';
  return '<label style="display:flex;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid #F4F2EC;cursor:pointer"><input type="checkbox" id="'+id+'"'+(checked?' checked':'')+'><span style="flex:1;font-size:14px">'+label+'</span><span class="chip" style="background:'+tc+'">'+tag+'</span></label>';}
function showOnboarding(){chat.innerHTML='';
  el('<div class="card" style="text-align:center;padding:26px 18px"><div style="font-size:42px;margin-bottom:6px">💚</div><div style="font-size:21px;font-weight:800;margin-bottom:6px">마이헬스케어</div><div class="psub" style="line-height:1.55">묻기 전에 챙길 것을 먼저 알려주는 건강 정보 도우미예요.<br><b>진단·처방은 하지 않아요.</b></div></div>');
  var co=el('<div class="card"><div class="tlab"><i class="ti ti-shield-check"></i>시작 전 동의</div>'
    +'<div class="psub" style="margin-bottom:8px">필요한 항목에 동의해 주세요. 동의는 \'내 정보\'에서 언제든 바꿀 수 있어요.</div>'
    +consentRow('c_terms','서비스 이용·개인정보 처리','필수',true)
    +consentRow('c_sensitive','민감정보(건강상태) 활용','선택',false)
    +consentRow('c_loc','위치 정보(가까운 약국 찾기)','선택',false)
    +consentRow('c_push','푸시 알림(체크인 리마인더)','선택',false)
    +'<div class="hob full" id="obStart" style="justify-content:center;margin-top:14px"><i class="ti ti-arrow-right"></i>동의하고 시작</div></div>');
  co.querySelector('#obStart').onclick=function(){
    if(!co.querySelector('#c_terms').checked){alert('서비스 이용·개인정보 처리 동의는 필수예요.');return;}
    var cons={terms:true,sensitive:co.querySelector('#c_sensitive').checked,loc:co.querySelector('#c_loc').checked,push:co.querySelector('#c_push').checked};
    try{localStorage.setItem('mhc_consent',JSON.stringify(cons));if(cons.loc)localStorage.setItem('mhc_loc_consent','1');}catch(e){}
    showPhrStep();};}
function showPhrStep(){chat.innerHTML='';
  el('<div class="card" style="text-align:center;padding:20px"><div style="font-size:34px">🩺</div><div style="font-size:17px;font-weight:800;margin-top:4px">건강 데이터 연동</div></div>');
  var pc=el('<div class="card"><div class="psub" style="margin-bottom:10px;line-height:1.55">건강검진·웨어러블 데이터를 연동하면 <b>묻기 전에 챙길 것</b>을 더 정확히 알려드려요. (선택 · 민감정보 동의 범위에서만 사용)</div>'
    +'<div class="hob full" id="phrYes" style="justify-content:center"><i class="ti ti-plug-connected"></i>연동하기</div>'
    +'<div class="hob soft" id="phrNo" style="justify-content:center;margin-top:8px">나중에 할게요</div></div>');
  pc.querySelector('#phrYes').onclick=function(){try{localStorage.setItem('mhc_phr','1');}catch(e){}finishOnboarding();};
  pc.querySelector('#phrNo').onclick=finishOnboarding;}
function finishOnboarding(){try{localStorage.setItem('mhc_onboarded','1');}catch(e){}afterPersona();}
function afterPersona(){chat.innerHTML='';
  el('<div class="ba"><div class="av"><i class="ti ti-sparkles"></i></div><div class="bx">안녕하세요. 안 물어보셔도 <b>오늘 챙길 것</b>을 먼저 알려드릴게요. 무엇이든 물어보셔도 좋아요. <b>진단·처방은 하지 않아요.</b></div></div>');
  if(localStorage.getItem('mhc_phr')){el('<div style="margin:-2px 0 6px 37px"><span class="chip" style="background:rgba(14,138,107,.12);color:#0B5F4A"><i class="ti ti-circle-check-filled"></i> 건강 데이터 연동됨</span></div>');}
  loadAnticipatory();showProfileSuggest();}
function loadAnticipatory(){fetch('/coaching/anticipatory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({persona_id:psel.value})}).then(r=>r.json()).then(a=>{
  if(a.top){var t=a.top,emg=(t.referral==='emergency'),col=emg?'#C0392B':'#B5721A';
   var c=el('<div class="card"></div>');
   c.style.borderColor=emg?'rgba(192,57,43,.3)':'rgba(224,162,62,.3)';c.style.background=emg?'rgba(192,57,43,.06)':'rgba(224,162,62,.1)';
   c.innerHTML='<div class="tlab" style="color:'+col+'"><i class="ti '+(emg?'ti-urgent':'ti-alert-triangle')+'"></i>지금 챙기세요</div><div class="ph">'+esc(t.text)+'</div>'+(t.note?'<div class="psub">'+esc(t.note)+'</div>':'');
   if(a.referral){var fb=document.createElement('div');fb.style.cssText='display:flex;gap:8px;margin-top:10px';
     [['hospital','가까운 병원 찾기'],['pharmacy','가까운 약국 찾기']].forEach(function(p){var b=document.createElement('div');b.className='hob soft';b.innerHTML='<i class="ti ti-map-pin"></i>'+p[1];b.onclick=(function(k){return function(){openFinder(k);};})(p[0]);fb.appendChild(b);});c.appendChild(fb);}}
  if(a.questions&&a.questions.length){var w=el('<div style="margin:0 0 4px 37px"></div>');a.questions.forEach(function(x){var ch=document.createElement('span');ch.className='chip';ch.style.cursor='pointer';ch.style.marginRight='6px';ch.textContent=x;ch.onclick=function(){qi.value=x;ask();};w.appendChild(ch);});}
 }).catch(function(e){});}
function openL(u){try{window.open(u,'_blank');}catch(e){}}
function openFinder(kind){
  var c=el('<div class="card"></div>');
  var title=(kind==='hospital'?'가까운 병원':'가까운 약국')+' 찾기';
  c.innerHTML='<div class="tlab"><i class="ti ti-map-pin"></i>'+title+'</div>'
   +'<div class="hob full" id="geoBtn" style="margin-bottom:6px"><i class="ti ti-current-location"></i>내 위치로 찾기</div>'
   +'<div style="display:flex;gap:8px;margin-bottom:6px"><input id="loc" style="flex:1;border:1px solid rgba(0,0,0,.1);border-radius:10px;padding:10px 12px;font-size:13.5px;font-family:inherit" value="역삼동" placeholder="또는 동네 입력(데모)"><div class="hob soft" id="fbtn">동네로</div></div>'
   +'<div class="psub" style="margin-bottom:8px"><i class="ti ti-lock"></i> 위치는 검색에만 쓰고 저장하지 않아요</div><div id="flist"></div>';
  var host=function(){return c.querySelector('#flist');};
  var post=function(body,label){host().innerHTML='<div class="psub">'+esc(label)+'</div>';
    fetch('/facilities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(r=>r.json()).then(function(d){renderFacilities(host(),d);}).catch(function(e){host().innerHTML='<div class="psub">조회 오류</div>';});};
  function geoGo(){
    if(!navigator.geolocation){post({kind:kind,region:'내 주변'},'위치 미지원 — 데모로');return;}
    host().innerHTML='<div class="psub">내 위치 확인 중…</div>';
    navigator.geolocation.getCurrentPosition(
      function(p){post({kind:kind,lat:p.coords.latitude,lon:p.coords.longitude,radius:2000},'내 주변에서 찾는 중…');},
      function(e){post({kind:kind,region:(c.querySelector('#loc').value||'내 주변')},'위치 권한 없음 — 동네(데모)로');});}
  c.querySelector('#geoBtn').onclick=function(){
    if(localStorage.getItem('mhc_loc_consent')==='1'){geoGo();return;}
    host().innerHTML='<div style="padding:12px;background:#FBF6EC;border-radius:10px">'
      +'<div style="font-weight:700;margin-bottom:6px"><i class="ti ti-map-pin"></i> 위치 정보 사용 동의</div>'
      +'<div class="psub" style="margin-bottom:10px;line-height:1.5">가까운 약국·병원을 찾기 위해 현재 위치를 사용해요. 위치는 <b>검색에만</b> 쓰고 저장하지 않아요 (위치정보법 안내 · 언제든 철회 가능).</div>'
      +'<div style="display:flex;gap:8px"><div class="hob full" id="locYes">동의하고 찾기</div><div class="hob soft" id="locNo">취소</div></div></div>';
    host().querySelector('#locYes').onclick=function(){localStorage.setItem('mhc_loc_consent','1');geoGo();};
    host().querySelector('#locNo').onclick=function(){host().innerHTML='<div class="psub">동네 입력으로 찾거나, 동의 후 위치로 찾을 수 있어요.</div>';};};
  c.querySelector('#fbtn').onclick=function(){post({kind:kind,region:(c.querySelector('#loc').value||'내 주변')},'동네(데모)에서 찾는 중…');};
}
function renderFacilities(host,d){
  if(d.error||!d.items||!d.items.length){host.innerHTML='<div class="psub">결과가 없어요</div>';return;}
  var src=d.real?'<span class="chip" style="background:rgba(14,138,107,.12);color:#0B5F4A"><i class="ti ti-circle-check-filled"></i> 실데이터·'+esc(d.source||'')+'</span>'
               :'<span class="chip" style="background:rgba(224,162,62,.16);color:#9A6B16">데모 데이터</span>';
  host.innerHTML='<div style="margin-bottom:8px">'+src+'</div>'+d.items.map(function(f){
    var badge='';
    if(f.open_now===true) badge='<span class="chip" style="background:rgba(14,138,107,.12);color:#0B5F4A">지금 영업중</span>';
    else if(f.open_now===false) badge='<span class="chip" style="background:rgba(0,0,0,.06);color:#8A887F">영업 종료</span>';
    var dept=f.dept?' <span style="font-weight:400;color:#8A887F;font-size:12px">'+esc(f.dept)+'</span>':'';
    var loc=esc(f.area||'')+(f.addr?' · '+esc(f.addr):'')+(f.hours?' · '+esc(f.hours):'');
    return '<div style="padding:12px 0;border-bottom:1px solid #F2F0E9">'
      +'<div style="display:flex;align-items:center;gap:8px"><b style="flex:1;font-size:14.5px">'+esc(f.name)+dept+'</b>'+badge+'</div>'
      +'<div class="psub" style="margin:4px 0 6px"><b style="color:#0E8A6B">'+esc(f.dist_label||'')+'</b> · '+loc+'</div>'
      +(f.hours_note?'<div class="psub" style="margin:0 0 8px;color:#B0833A"><i class="ti ti-clock-question"></i> '+esc(f.hours_note)+'</div>':'')
      +'<a href="'+f.map_url+'" target="_blank" rel="noopener" class="chip" style="text-decoration:none"><i class="ti ti-map-2"></i>지도</a> '
      +'<a href="'+f.tel_url+'" class="chip" style="text-decoration:none;margin-left:5px"><i class="ti ti-phone"></i>전화</a></div>';
  }).join('')+'<div class="psub" style="margin-top:9px;line-height:1.5">'+esc(d.notice||'')+'</div>';}
function loadProfile(){try{return JSON.parse(localStorage.getItem('mhc_profile')||'{}');}catch(e){return {};}}
function saveProfile(p){try{localStorage.setItem('mhc_profile',JSON.stringify(p));}catch(e){}}
function openProfile(){
  var pf=loadProfile();
  var ages=['','20대 미만','20대','30대','40대','50대','60대','70대 이상'],sexes=['선택안함','남','여'];
  var topics=['혈압','혈당','콜레스테롤','체중','수면','운동','식단','스트레스'],conds=['고혈압','당뇨','고지혈증','비만'];
  function opt(a,s){return a.map(function(x){return '<option'+(x===s?' selected':'')+'>'+(x||'연령대')+'</option>';}).join('');}
  function chip(a,s,g){return a.map(function(x){return '<span class="pchip'+((s||[]).indexOf(x)>=0?' on':'')+'" data-v="'+x+'" data-g="'+g+'">'+x+'</span>';}).join('');}
  var c=el('<div class="card"><div class="tlab"><i class="ti ti-user-heart"></i>내 건강 정보</div>'
    +'<div class="psub" style="margin-bottom:8px">입력하면 나에게 맞는 상세 질문을 추천해드려요. 진단·처방은 하지 않아요.</div>'
    +'<div style="display:flex;gap:8px;margin-bottom:8px"><select id="pfAge" style="flex:1;padding:9px;border-radius:9px;border:1px solid rgba(0,0,0,.12);font-family:inherit">'+opt(ages,pf.age_band||'')+'</select>'
    +'<select id="pfSex" style="flex:1;padding:9px;border-radius:9px;border:1px solid rgba(0,0,0,.12);font-family:inherit">'+opt(sexes,pf.sex||'선택안함')+'</select></div>'
    +'<div class="psub" style="margin:6px 0 4px">관심 건강 주제</div><div style="display:flex;flex-wrap:wrap;gap:6px">'+chip(topics,pf.topics,'t')+'</div>'
    +'<label style="display:flex;align-items:center;gap:8px;margin:12px 0 4px;font-size:13px;cursor:pointer"><input type="checkbox" id="pfC"'+(pf.sensitive_consent?' checked':'')+'> 기저질환 입력에 동의 <span class="psub">(민감정보 · 동의 시에만 사용)</span></label>'
    +'<div id="pfCW" style="display:'+(pf.sensitive_consent?'block':'none')+'"><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">'+chip(conds,pf.conditions,'c')+'</div></div>'
    +'<div class="hob full" style="justify-content:center;margin-top:14px" id="pfSave"><i class="ti ti-device-floppy"></i>저장하고 추천 받기</div>'
    +'<div class="hob soft" id="pfReset" style="justify-content:center;margin-top:8px"><i class="ti ti-adjustments"></i>동의·연동 다시 설정</div>'
    +'<div id="pfOut" style="margin-top:12px"></div></div>');
  c.querySelector('#pfReset').onclick=function(){try{localStorage.removeItem('mhc_onboarded');}catch(e){}showOnboarding();};
  c.querySelectorAll('.pchip').forEach(function(ch){ch.onclick=function(){ch.classList.toggle('on');};});
  c.querySelector('#pfC').onchange=function(){c.querySelector('#pfCW').style.display=this.checked?'block':'none';};
  c.querySelector('#pfSave').onclick=function(){
    var pick=function(g){return [].slice.call(c.querySelectorAll('.pchip.on[data-g="'+g+'"]')).map(function(x){return x.getAttribute('data-v');});};
    var con=c.querySelector('#pfC').checked;
    var prof={age_band:c.querySelector('#pfAge').value,sex:c.querySelector('#pfSex').value,topics:pick('t'),sensitive_consent:con,conditions:con?pick('c'):[]};
    saveProfile(prof);var out=c.querySelector('#pfOut');out.innerHTML='<div class="psub">추천 질문을 준비하고 있어요…</div>';
    fetch('/profile/suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(prof)}).then(r=>r.json()).then(function(d){renderSuggest(out,d);}).catch(function(e){out.innerHTML='';});};}
function renderSuggest(host,d){
  var sum=d.summary?'<div class="psub" style="margin-bottom:8px"><i class="ti ti-user-check"></i> 내 정보: '+esc(d.summary)+'</div>':'';
  host.innerHTML=sum+'<div class="psub" style="margin-bottom:6px">나에게 맞는 상세 질문 — 눌러서 물어보세요</div><div id="sgw" style="display:flex;flex-wrap:wrap;gap:6px"></div>';
  var w=host.querySelector('#sgw');(d.questions||[]).forEach(function(q){var s=document.createElement('span');s.className='chip';s.style.cursor='pointer';s.textContent=q;s.onclick=function(){qi.value=q;ask();};w.appendChild(s);});}
function showProfileSuggest(){var pf=loadProfile();var has=(pf.topics&&pf.topics.length)||(pf.conditions&&pf.conditions.length);if(!has)return;
  fetch('/profile/suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pf)}).then(r=>r.json()).then(function(d){var c=el('<div class="card"></div>');renderSuggest(c,d);}).catch(function(e){});}
function ask(){var q=qi.value.trim();if(!q)return;qi.value='';el('<div class="bu">'+esc(q)+'</div>');send(q);}
function send(q){
  var ab=el('<div class="ba"><div class="av"><i class="ti ti-sparkles"></i></div><div class="bx">…</div></div>');
  var box=ab.querySelector('.bx');var text='',hoff=null,pinj=null,cc=0;
  fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({query:q,persona_id:psel.value,conversation_id:'app-'+Date.now()})})
  .then(res=>{var rd=res.body.getReader(),dec=new TextDecoder(),buf='';
   (function pump(){return rd.read().then(({value,done})=>{if(done){finish();return;}
     buf+=dec.decode(value,{stream:true});var i;
     while((i=buf.indexOf('\n\n'))>=0){var ln=buf.slice(0,i);buf=buf.slice(i+2);
      var m=ln.match(/^data: (.*)$/s);if(!m)return;var ev;try{ev=JSON.parse(m[1]);}catch(e){continue;}
      if(ev.type==='INFO'&&ev.data&&ev.data.search_results)cc=ev.data.search_results.length;
      else if(ev.type==='GENERATION'){text+=(ev.text||'');box.innerHTML=cites(text);chat.scrollTop=chat.scrollHeight;}
      else if(ev.type==='STOP'){if(ev.handoff)hoff=ev.handoff;if(ev.personal_injected&&ev.personal_injected.length)pinj=ev.personal_injected;}
      else if(ev.type==='ERROR'){box.innerHTML='<span style="color:#C0392B">요청 오류 — 잠시 후 다시 시도해 주세요.</span>';}}
     return pump();});})();
   function finish(){if(!text)box.innerHTML='(빈 응답)';
     if(pinj)el('<div class="meta">🔐 개인맥락 반영됨 — '+esc(pinj.join(', '))+'</div>');
     if(cc)el('<div class="meta">근거 '+cc+'개</div>');
     if(hoff&&hoff.referral==='emergency')el('<div class="emg">🚑 응급 시 즉시 119·응급실</div>');
     if(hoff&&hoff.show){var sft=hoff.copy==='soft';
       var w=el('<div class="ho"></div>');
       var b=document.createElement('button');b.className='hob '+(sft?'soft':'full');
       b.innerHTML='<i class="ti ti-flame"></i>'+esc(hoff.label||'실천 코칭 받기');
       b.onclick=function(){w.remove();startCoaching();};w.appendChild(b);
       if(hoff.banner){var sp=document.createElement('div');sp.className='meta';sp.style.margin='0';sp.textContent='진료와 병행 권장';w.appendChild(sp);}}}
  }).catch(e=>{box.innerHTML='<span style="color:#C0392B">연결 오류</span>';});}
function startCoaching(){
  el('<div class="card"><div class="tlab"><i class="ti ti-flame"></i>실천 코칭</div>'
    +'<div class="qh">어느 쪽을 도와드릴까요?</div><div class="trk">'
    +'<div class="tk on" onclick="selectTrack(\'diet\')"><i class="ti ti-salad"></i>식단</div>'
    +'<div class="tk" onclick="selectTrack(\'exercise\')"><i class="ti ti-run"></i>운동</div>'
    +'<div class="tk" onclick="selectTrack(\'habit\')"><i class="ti ti-bed"></i>생활습관</div></div></div>');}
function selectTrack(t){_track=t;askIntake();}
var _ans={},_qi=0;
function askIntake(){_ans={};_qi=0;renderQ();}
function renderQ(){var Q=INTAKE_BY_TRACK[_track]||INTAKE_BY_TRACK.diet;
  if(_qi>=Q.length){return getPlan();}
  var it=Q[_qi];var pct=Math.round(_qi/Q.length*100);
  var c=el('<div class="card"><div class="prog"><div style="width:'+pct+'%"></div></div>'
    +'<div class="qh">'+esc(it.q)+'</div><div id="opts"></div></div>');
  var host=c.querySelector('#opts');
  it.o.forEach(function(o){var b=document.createElement('button');b.className='opt';b.textContent=o;
    b.onclick=function(){_ans[it.id]=o;_qi++;renderQ();};host.appendChild(b);});}
function getPlan(){
  var load=el('<div class="card"><div class="qh" style="margin:0;color:#8A887F;font-size:14px">맞춤 플랜을 만들고 있어요…</div></div>');
  fetch('/coaching/plan',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({persona_id:psel.value,track:_track,intake:_ans})})
  .then(r=>r.json()).then(p=>{load.remove();renderPlan(p);})
  .catch(e=>{load.querySelector('.qh').textContent='플랜 생성 오류';});}
var _plan=null,_daily=[],_gami=null;
function renderPlan(p){
  if(p.error){el('<div class="card"><div class="qh">플랜 오류</div><div class="psub">'+esc(p.error)+'</div></div>');return;}
  _plan=p;_daily=[];
  var tl={diet:'식단',exercise:'운동',habit:'생활습관'}[_track]||'';
  var items=(p.items||[]).map(function(it){return '<div class="it"><i class="ti ti-square"></i><span style="flex:1">'+esc(it.text)+'</span></div>';}).join('');
  var cites=(p.items||[]).map(function(it){return esc(it.cite);}).filter((v,i,a)=>a.indexOf(v)===i).join(' · ');
  var ban=p.banner?'<div class="ban"><i class="ti ti-alert-triangle"></i><div>'+esc(p.banner)+'</div></div>':'';
  el('<div class="card"><div class="tlab"><i class="ti ti-checklist"></i>2주 '+tl+' 챌린지</div>'
    +'<div class="ph">'+esc(p.header)+'</div><div class="psub">'+esc(p.tone||'')+'</div>'
    +items+'<div class="icite">근거 · '+cites+'</div>'+ban
    +'<div class="hob full" style="justify-content:center;margin-top:14px" onclick="startChallenge()"><i class="ti ti-check"></i>2주 챌린지 시작하기</div></div>');}
var _lastCk='',_ciBtn=null;
function ckey(){return 'mhc_ck_'+(psel.value||'')+'_'+(_track||'');}
function loadCk(){try{return JSON.parse(localStorage.getItem(ckey())||'{}');}catch(e){return {};}}
function saveCk(){try{localStorage.setItem(ckey(),JSON.stringify({daily:_daily,date:_lastCk}));}catch(e){}}
function todayStr(){return new Date().toISOString().slice(0,10);}
function markCk(){if(_ciBtn&&_lastCk===todayStr()){_ciBtn.innerHTML='<i class="ti ti-circle-check-filled"></i>오늘 체크인 완료 ✓';_ciBtn.style.opacity='.6';}}
function startChallenge(){
  var p=_plan,sv=loadCk();_daily=sv.daily||[];_lastCk=sv.date||'';
  var acts=(p.items||[]).map(function(it){return '<div data-done="0" onclick="toggleAct(this)" style="display:flex;align-items:center;gap:8px;padding:9px 0;cursor:pointer;border-bottom:1px solid #F4F2EC"><i class="ti ti-circle" style="color:#0E8A6B"></i><span style="flex:1;font-size:14px">'+esc(it.text)+'</span></div>';}).join('');
  var resumed=(_daily.filter(Boolean).length)?'<div class="psub" style="margin-bottom:6px;color:#0B5F4A"><i class="ti ti-history"></i> 이어가기 — 지금까지 '+_daily.filter(Boolean).length+'일 실천했어요</div>':'';
  var c=el('<div class="card"><div class="tlab"><i class="ti ti-flame"></i>오늘의 실천 · 지속 루프</div>'
    +resumed+'<div class="psub" style="margin-bottom:6px">매일 실천하고 체크인하면 스트릭이 쌓여요</div>'+acts
    +'<div class="hob full" id="ciBtn" style="justify-content:center;margin-top:12px" onclick="checkinToday()"><i class="ti ti-calendar-check"></i>오늘 체크인 완료</div>'
    +'<div id="gami" style="margin-top:14px"></div>'
    +'<div class="psub" style="margin-top:10px"><a href="javascript:void(0)" onclick="demoFill()" style="color:#0E8A6B;font-weight:600">데모: 지난 6일 채우기</a> · 이 기기에 저장돼요(localStorage)</div></div>');
  _gami=c.querySelector('#gami');_ciBtn=c.querySelector('#ciBtn');markCk();refreshGami();}
function toggleAct(e){var on=e.getAttribute('data-done')==='1';e.setAttribute('data-done',on?'0':'1');
  e.querySelector('i').className=on?'ti ti-circle':'ti ti-circle-check-filled';
  var sp=e.querySelector('span');sp.style.textDecoration=on?'none':'line-through';sp.style.color=on?'':'#A8A599';}
function checkinToday(){if(_lastCk===todayStr())return;_daily.push(true);_lastCk=todayStr();saveCk();markCk();refreshGami();
  if(_plan&&_plan.plan_id){try{fetch('/coaching/checkin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_id:_plan.plan_id,done:true})});}catch(e){}}}
function demoFill(){_daily=[true,true,true,true,true,true].concat(_daily);saveCk();refreshGami();}
function refreshGami(){if(!_gami)return;var days=(_plan&&_plan.plan_days)||14;
  fetch('/coaching/summary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({daily_done:_daily,plan_days:days})})
  .then(r=>r.json()).then(function(s){renderGami(s);}).catch(function(e){});}
function renderGami(s){
  var bd=(s.badges||[]).map(function(b){return '<span class="chip" style="background:rgba(14,138,107,.12);color:#0B5F4A;margin:2px 3px 0 0">🏅 '+esc(b)+'</span>';}).join('');
  var pct=Math.min(100,Math.round((s.adherence||0)/70*100));
  var comp=s.completed?'<div class="ban" style="background:rgba(14,138,107,.1);border-color:rgba(14,138,107,.35);color:#0B5F4A;margin-top:10px"><i class="ti ti-trophy"></i><div>첫 완주 달성! 꾸준함이 멋져요 🎉</div></div>':'';
  var coach=(s.coach&&s.coach.message&&!s.completed)?'<div style="margin-top:10px;padding:10px 12px;background:#F2F8F5;border-radius:10px;font-size:13.5px;color:#0B5F4A;line-height:1.45"><i class="ti ti-message-heart"></i> '+esc(s.coach.message)+'</div>':'';
  _gami.innerHTML='<div style="display:flex;gap:8px;text-align:center">'
    +'<div style="flex:1;background:#FBF4E8;border-radius:12px;padding:10px 4px"><div style="font-size:21px;font-weight:800;color:#E0822E">🔥'+s.streak+'</div><div class="psub">연속일</div></div>'
    +'<div style="flex:1;background:#EEF6F2;border-radius:12px;padding:10px 4px"><div style="font-size:21px;font-weight:800;color:#0E8A6B">'+s.points+'</div><div class="psub">포인트</div></div>'
    +'<div style="flex:1;background:#F1EEFA;border-radius:12px;padding:10px 4px"><div style="font-size:21px;font-weight:800;color:#6A53B0">Lv.'+s.level+'</div><div class="psub">레벨</div></div></div>'
    +'<div style="margin-top:10px"><div class="psub">완주까지 '+(s.adherence||0)+'% / 70%</div><div class="prog" style="margin-top:4px"><div style="width:'+pct+'%"></div></div></div>'
    +(bd?'<div style="margin-top:10px">'+bd+'</div>':'')+coach+comp;}
qi.addEventListener('keydown',function(e){if(e.key==='Enter'){ask();}});
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
        if self.path in ("/app", "/app/"):     # 확정 디자인(Warm Light) 앱
            return self._send(200, APP_PAGE, "text/html; charset=utf-8")
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
        if self.path == "/coaching/plan":      # 코칭 플랜(로컬 coaching_engine — 식단/운동/습관)
            req = self._read_body()
            p = _persona_by_id(load_personas(), req.get("persona_id"))
            if not p:
                return self._send(404, json.dumps({"error": "unknown persona"}))
            try:
                import wellness_router as _wr, coaching_engine as _ce
                pv = compute_preview(p, "혈압 건강 관리")
                band = _wr.worst_band([f.get("label_user") for f in pv.get("findings", [])])
                track = req.get("track") or "diet"
                plan = _ce.generate_plan(track, req.get("intake") or {}, band)
                try:                                  # 서버 영속(비식별, 비치명) → plan_id 동봉
                    sess = _rag_persist("/api/rag/coaching/session",
                                        {"track": track, "band": band, "mode": "medical"})
                    sid = (sess or {}).get("session_id")
                    if sid:
                        items = [{"text": it.get("text"), "key": it.get("key")}
                                 for it in plan.get("items", [])]
                        pr = _rag_persist("/api/rag/coaching/plan",
                                          {"session_id": sid, "track": track, "items": items,
                                           "band": band, "banner": plan.get("banner"),
                                           "compliance_action": plan.get("compliance_action", "pass")})
                        if pr and pr.get("plan_id"):
                            plan["plan_id"] = pr["plan_id"]
                            plan["session_id"] = sid
                except Exception:
                    pass
                return self._send(200, json.dumps(plan, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
        if self.path == "/coaching/anticipatory":   # 선제 '오늘 챙길 것' + 예상질문 + referral
            req = self._read_body()
            p = _persona_by_id(load_personas(), req.get("persona_id"))
            if not p:
                return self._send(404, json.dumps({"error": "unknown persona"}))
            try:
                import wellness_router as _wr, anticipatory_engine as _ae, referral as _rf
                pv = compute_preview(p, "혈압 건강")
                band = _wr.worst_band([f.get("label_user") for f in pv.get("findings", [])])
                sig = {"band": band, "warning_days": 3 if band in ("주의", "경고") else 0}
                top = _ae.top(sig)
                ref = _rf.referral(band=band) if (top and top.get("referral")) else None
                out = {"band": band, "top": top, "questions": _ae.anticipated_questions(sig), "referral": ref}
                return self._send(200, json.dumps(out, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
        if self.path == "/coaching/summary":        # 게이미피케이션 요약 + 적응형 코칭 메시지
            req = self._read_body()
            try:
                import coaching_gamification as _g
                import coaching_adaptive as _ca
                dd = [bool(x) for x in (req.get("daily_done") or [])]
                days = int(req.get("plan_days") or 14)
                s = _g.summary(dd, days)
                dsl = 0                                   # 최근 연속 미실천일(이탈 신호)
                for d in reversed(dd):
                    if d:
                        break
                    dsl += 1
                s["coach"] = _ca.coach(s["adherence"], s["streak"],
                                       days_since_last=dsl, completed=s["completed"])
                return self._send(200, json.dumps(s, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
        if self.path == "/coaching/checkin":         # 체크인 서버 영속(plan_id) — RAG 전달, 비치명
            req = self._read_body()
            pid = req.get("plan_id")
            if not pid:
                return self._send(200, json.dumps({"persisted": False}, ensure_ascii=False))
            out = _rag_persist("/api/rag/coaching/checkin",
                               {"plan_id": pid, "done": bool(req.get("done", True)),
                                "item_key": req.get("item_key")})
            return self._send(200, json.dumps(out or {"persisted": False}, ensure_ascii=False))
        if self.path == "/profile/suggest":          # 프로필 → 상세 질문 추천(정보 탐색)
            req = self._read_body()
            try:
                import suggested_questions as _sq
                conds = req.get("conditions") if req.get("sensitive_consent") else None
                out = {"questions": _sq.suggest(req.get("topics"), conds),
                       "summary": _sq.profile_summary(req)}
                return self._send(200, json.dumps(out, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
        if self.path == "/facilities":               # 가까운 병원·약국(거리·영업시간) §5.8
            req = self._read_body()
            kind = req.get("kind") or "pharmacy"
            lat, lon = req.get("lat"), req.get("lon")
            try:
                if lat is not None and lon is not None:   # 좌표 → 심평원(HIRA) 실데이터
                    try:
                        import kr_facilities as _kr
                        real = _kr.find_real(kind, lat, lon, radius=int(req.get("radius") or 2000))
                        if real.get("supported"):
                            real["real"] = True
                            return self._send(200, json.dumps(real, ensure_ascii=False))
                    except Exception:
                        pass                               # 실패 → 데모 폴백
                import facility_finder as _ff
                out = _ff.find_demo(kind, region=req.get("region"))
                out["real"] = False
                return self._send(200, json.dumps(out, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
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
    # Cloud Run: PORT 환경변수 + 0.0.0.0 바인딩(공개). 로컬: 127.0.0.1.
    on_cloud = bool(os.environ.get("K_SERVICE") or os.environ.get("PORT"))
    port = int(os.environ.get("PORT", args.port))
    host = "0.0.0.0" if on_cloud else "127.0.0.1"

    tok_note = None
    if ".run.app" in Handler.rag_url:  # 클라우드 대상이면 토큰 가용성 점검
        tok_note = "발급 OK" if get_id_token(audience=Handler.rag_url) else "실패(gcloud 로그인/SA 필요)"
    print("=" * 60)
    print(" 페르소나 개인화 테스트 서버")
    print(f"  페르소나 : {len(data.get('personas', []))}개  ({PERSONAS_PATH.name})")
    print(f"  대상 RAG : {Handler.rag_url or '(없음 - 미리보기 전용, --preview)'}")
    if tok_note:
        print(f"  토큰     : {tok_note}")
    print(f"  바인드   : {host}:{port}")
    print("  종료     : Ctrl+C")
    print("=" * 60)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
