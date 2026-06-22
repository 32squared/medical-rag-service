"""admin_server.py — RAG 운영 어드민 대시보드 (비밀번호 보호, 공개 ingress).

답변속도·토큰·대화통계·최근쿼리(원문)·프롬프트를 보여준다. 데이터는 RAG 서비스의
/api/rag/admin/* 집계 엔드포인트를 서버-대-서버(IAM 토큰 + X-Admin-Secret)로 호출해 받는다.
사람 접근은 ADMIN_PASSWORD 쿠키 게이트로 보호.

env: RAG_DEV_URL(대상 RAG), ADMIN_SECRET(엔드포인트 공유 비밀), ADMIN_PASSWORD(로그인),
     PORT, K_SERVICE(Cloud Run 감지).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote
import urllib.request
import urllib.error

RAG_URL = (os.environ.get("RAG_DEV_URL")
           or "https://medical-rag-dev-716262961556.asia-northeast3.run.app").rstrip("/")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
_SID = hashlib.sha256(("mha-admin|" + ADMIN_PASSWORD).encode()).hexdigest() if ADMIN_PASSWORD else ""

_token = {}


def get_id_token(audience=None):
    key = audience or "_"
    now = time.time()
    c = _token.get(key)
    if c and now - c[1] < 2400:
        return c[0]
    tok = None
    if os.environ.get("K_SERVICE"):
        try:
            req = urllib.request.Request(
                "http://metadata.google.internal/computeMetadata/v1/instance/"
                "service-accounts/default/identity?audience=" + quote(audience or "", safe=""),
                headers={"Metadata-Flavor": "Google"})
            tok = urllib.request.urlopen(req, timeout=5).read().decode().strip() or None
        except Exception as e:
            sys.stderr.write(f"[token] {e}\n")
    if tok:
        _token[key] = (tok, now)
    return tok


def rag_get(path_qs):
    """RAG admin 엔드포인트 GET 프록시 (IAM 토큰 + X-Admin-Secret)."""
    url = f"{RAG_URL}{path_qs}"
    h = {"X-Admin-Secret": ADMIN_SECRET,
         "X-User-Id": "admin", "X-User-Role": "admin", "X-User-Permissions": "manage_kb"}
    if ".run.app" in RAG_URL:
        tok = get_id_token(audience=RAG_URL)
        if tok:
            h["Authorization"] = "Bearer " + tok
    req = urllib.request.Request(url, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


PAGE = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>마이헬스케어 — RAG 어드민</title>
<style>
:root{--b:#e6e4da;--mut:#6b6a64;--ink:#26261f;--grn:#0f6e56;--red:#c62828;--amb:#b06a00}
*{box-sizing:border-box}body{font-family:'Malgun Gothic','Segoe UI',sans-serif;margin:0;color:var(--ink);background:#faf9f5}
.wrap{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mut);font-size:12px}
.bar{display:flex;gap:8px;align-items:center;margin:12px 0}
select,button{font:inherit;padding:5px 9px;border:1px solid var(--b);border-radius:8px;background:#fff;cursor:pointer}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0}
.card{border:1px solid var(--b);border-radius:12px;background:#fff;padding:11px 13px}
.card .k{font-size:12px;color:var(--mut)}.card .v{font-size:22px;font-weight:700;margin-top:3px}
.card .s{font-size:11px;color:var(--mut);margin-top:2px}
.sec{border:1px solid var(--b);border-radius:12px;background:#fff;padding:12px 14px;margin:12px 0}
.sec h2{font-size:14px;margin:0 0 8px;color:var(--grn)}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{border-bottom:1px solid #eee;padding:5px 7px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600}
.barrow{display:flex;align-items:center;gap:6px;margin:3px 0;font-size:12px}
.barrow .lab{min-width:120px}.barrow .bg{flex:1;background:#f0efe9;border-radius:5px;height:14px;overflow:hidden}
.barrow .fill{height:100%;background:#1d9e75}
pre{white-space:pre-wrap;font-size:11px;background:#f6f5f0;border:1px solid var(--b);border-radius:8px;padding:10px;max-height:340px;overflow:auto}
.q{color:#1f4e79}.a{color:#333}
.login{max-width:320px;margin:14vh auto;text-align:center}
.login input{font:inherit;padding:8px 10px;border:1px solid var(--b);border-radius:8px;width:100%;margin:8px 0}
.pill{display:inline-block;font-size:11px;border-radius:6px;padding:1px 6px}
.warn{background:#fbe9e9;color:#c62828}.ok{background:#e7f3e8;color:#2e7d32}
</style></head><body><div class=wrap>
<div style="display:flex;justify-content:space-between;align-items:baseline">
 <div><h1>마이헬스케어 — RAG 운영 어드민</h1><div class=sub>답변속도 · 토큰 · 대화 통계 · 프롬프트 · 최근 쿼리</div></div>
 <a href="/logout" style="font-size:12px;color:#888">로그아웃</a></div>
<div class=bar>구간 <select id=days onchange=load()>
 <option value=7>최근 7일</option><option value=30 selected>최근 30일</option><option value=90>최근 90일</option></select>
 <button onclick=load()>새로고침</button><span id=note class=sub></span></div>
<div class=cards id=cards></div>
<div class=sec><h2>구간별 (일자)</h2><div id=ts></div></div>
<div class=sec><h2>대화 통계</h2><div id=stats></div></div>
<div class=sec><h2>최근 쿼리 (원문)</h2><div id=recent></div></div>
<div class=sec><h2>현재 시스템 프롬프트</h2><div id=prompt></div></div>
<script>
const $=id=>document.getElementById(id);
function n(x){return (x||0).toLocaleString()}
async function j(p){const r=await fetch(p);if(!r.ok)throw new Error(p+' '+r.status);return r.json()}
async function load(){
 const d=$('days').value; $('note').textContent='불러오는 중…';
 try{
  const [s,ts,st,rc,pr]=await Promise.all([
   j('/api/admin/summary?days='+d),j('/api/admin/timeseries?days='+d),
   j('/api/admin/stats?days='+d),j('/api/admin/recent?limit=50'),j('/api/admin/prompt')]);
  renderCards(s);renderTs(ts);renderStats(st);renderRecent(rc);renderPrompt(pr);
  $('note').textContent='단가 가정 $'+s.price_in_usd_per_m+'/$'+s.price_out_usd_per_m+' per 1M · 환율 '+n(s.fx_krw)+'원';
 }catch(e){$('note').textContent='오류: '+e.message}
}
function card(k,v,s){return '<div class=card><div class=k>'+k+'</div><div class=v>'+v+'</div><div class=s>'+(s||'')+'</div></div>'}
function renderCards(s){
 const L=s.latency_ms,T=s.tokens,C=s.cost_krw_est,F=s.feedback||{up:0,down:0};
 $('cards').innerHTML=
  card('쿼리 수',n(s.queries),s.days+'일')+
  card('평균 응답속도',(L.avg_total/1000).toFixed(1)+'s','검색 '+(L.avg_retrieval/1000).toFixed(1)+'s · LLM '+(L.avg_llm/1000).toFixed(1)+'s · 최대 '+(L.max_total/1000).toFixed(1)+'s')+
  card('총 토큰',n(T.sum_total),'입력 '+n(T.sum_in)+' · 출력 '+n(T.sum_out)+' · 평균 '+n(T.avg_in+T.avg_out)+'/쿼리')+
  card('추정 비용',n(C.total)+'원','쿼리당 '+C.per_query+'원 (가정 단가)')+
  card('피드백','👍 '+n(F.up)+' / 👎 '+n(F.down),'');
}
function renderTs(d){
 if(!d.series.length){$('ts').innerHTML='<div class=sub>데이터 없음</div>';return}
 let h='<table><tr><th>일자</th><th>쿼리</th><th>입력토큰</th><th>출력토큰</th><th>합계</th><th>평균속도</th><th>추정비용</th></tr>';
 for(const r of d.series.slice().reverse())h+='<tr><td>'+r.date+'</td><td>'+n(r.queries)+'</td><td>'+n(r.tokens_in)+'</td><td>'+n(r.tokens_out)+'</td><td>'+n(r.tokens_total)+'</td><td>'+(r.avg_latency_ms/1000).toFixed(1)+'s</td><td>'+n(r.cost_krw_est)+'원</td></tr>';
 $('ts').innerHTML=h+'</table>';
}
function bars(title,arr){
 const max=Math.max(1,...arr.map(x=>x.count));let h='<div style="font-size:12px;color:#888;margin:6px 0 2px">'+title+'</div>';
 for(const x of arr)h+='<div class=barrow><span class=lab>'+esc(x.label)+'</span><span class=bg><span class=fill style="width:'+(x.count/max*100)+'%"></span></span><span>'+n(x.count)+'</span></div>';
 return h;
}
function renderStats(d){
 $('stats').innerHTML=bars('근거 품질(evidence_quality)',d.evidence_quality)+bars('게이트 결정(gate_decision)',d.gate_decision)+bars('가드레일 액션(guardrail_action)',d.guardrail_action);
}
function renderRecent(d){
 let h='<table><tr><th>시각</th><th>질의 / 답변</th><th>토큰</th><th>속도</th><th>가드레일</th><th>근거</th></tr>';
 for(const r of d.rows)h+='<tr><td style="white-space:nowrap">'+esc(r.created_at.slice(0,19).replace("T"," "))+'</td>'+
   '<td><div class=q>🙋 '+esc(r.query)+'</div><div class=a>💬 '+esc(r.answer.slice(0,240))+(r.answer.length>240?'…':'')+'</div></td>'+
   '<td style="white-space:nowrap">in '+n(r.token_in)+'<br>out '+n(r.token_out)+'<br>'+r.cost_krw_est+'원</td>'+
   '<td style="white-space:nowrap">'+(r.latency_ms/1000).toFixed(1)+'s</td>'+
   '<td>'+esc(r.guardrail_action||'')+'</td><td>'+esc(r.evidence_quality||'')+'</td></tr>';
 $('recent').innerHTML=h+'</table>';
}
function renderPrompt(p){
 $('prompt').innerHTML='<div class=sub>모델 '+esc(p.model)+' · reasoning '+esc(p.reasoning_effort)+'</div><pre>'+esc(p.system_prompt_sample)+'</pre>';
}
function esc(s){return (s==null?'':''+s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
load();
</script></div></body></html>"""

LOGIN = """<!doctype html><html lang=ko><head><meta charset=utf-8><title>어드민 로그인</title>
<style>body{font-family:'Malgun Gothic',sans-serif;background:#faf9f5}.login{max-width:320px;margin:16vh auto;text-align:center}
input{font:inherit;padding:9px 11px;border:1px solid #ddd;border-radius:8px;width:100%;margin:8px 0}
button{font:inherit;padding:9px;border:0;border-radius:8px;background:#0f6e56;color:#fff;width:100%;cursor:pointer}
h1{font-size:18px}.m{color:#c62828;font-size:13px;min-height:18px}</style></head><body>
<form class=login method=post action=/login>
<h1>마이헬스케어 RAG 어드민</h1><div class=m>__MSG__</div>
<input type=password name=pw placeholder="관리자 비밀번호" autofocus>
<button>로그인</button></form></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _authed(self):
        if not _SID:
            return False
        ck = self.headers.get("Cookie") or ""
        return ("asid=" + _SID) in ck

    def _send(self, code, body, ctype="text/html; charset=utf-8", cookie=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass
        self.close_connection = True

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/logout":
            return self._send(200, LOGIN.replace("__MSG__", "로그아웃되었습니다."),
                              cookie="asid=; Max-Age=0; Path=/")
        if not self._authed():
            msg = "" if _SID else "서버에 ADMIN_PASSWORD가 설정되지 않았습니다."
            return self._send(200, LOGIN.replace("__MSG__", msg))
        if p.path == "/":
            return self._send(200, PAGE)
        if p.path.startswith("/api/admin/"):
            rag_path = "/api/rag/admin/" + p.path[len("/api/admin/"):]
            qs = ("?" + p.query) if p.query else ""
            try:
                data = rag_get(rag_path + qs)
                return self._send(200, data, "application/json; charset=utf-8")
            except urllib.error.HTTPError as e:
                return self._send(e.code, json.dumps({"error": f"RAG {e.code}"}),
                                  "application/json; charset=utf-8")
            except Exception as e:
                return self._send(502, json.dumps({"error": str(e)}),
                                  "application/json; charset=utf-8")
        return self._send(404, "not found")

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/login":
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
            pw = parse_qs(body).get("pw", [""])[0]
            if _SID and pw == ADMIN_PASSWORD:
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"asid={_SID}; Path=/; HttpOnly; Max-Age=43200")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                return
            return self._send(200, LOGIN.replace("__MSG__", "비밀번호가 올바르지 않습니다."))
        return self._send(404, "not found")


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    port = int(os.environ.get("PORT", "8780"))
    host = "0.0.0.0" if (os.environ.get("K_SERVICE") or os.environ.get("PORT")) else "127.0.0.1"
    print("=" * 56)
    print(" RAG 운영 어드민 대시보드")
    print(f"  대상 RAG : {RAG_URL}")
    print(f"  비밀번호 : {'설정됨' if _SID else '미설정(로그인 불가) — ADMIN_PASSWORD 필요'}")
    print(f"  시크릿   : {'설정됨' if ADMIN_SECRET else '미설정'}")
    print(f"  바인드   : {host}:{port}")
    print("=" * 56)
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    main()
