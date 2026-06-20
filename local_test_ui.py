#!/usr/bin/env python
"""
local_test_ui.py — 로컬 브라우저에서 클라우드 RAG(dev)를 눌러보는 테스트 UI.

브라우저는 Cloud Run의 IAM 토큰을 직접 만들 수 없으므로, 이 작은 로컬 서버가
중계한다: 브라우저 → http://localhost:8765 → (gcloud 토큰 + X-User 헤더 부착)
→ Cloud Run /api/rag/chat (SSE) → 스트리밍 그대로 브라우저로 전달.

사용:
  python local_test_ui.py                 # 기본 dev URL, http://localhost:8765
  python local_test_ui.py --port 9000
  python local_test_ui.py --rag-url https://...run.app

전제: gcloud 로그인(현재 계정). 토큰은 자동 발급·캐시(40분)된다.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

DEFAULT_RAG_URL = os.environ.get(
    "RAG_DEV_URL", "https://medical-rag-dev-716262961556.asia-northeast3.run.app"
)

_token = {"v": None, "at": 0.0}


def get_id_token(force=False):
    """gcloud로 identity token 발급(40분 캐시). Windows .cmd 대응 위해 shell=True."""
    now = time.time()
    if not force and _token["v"] and now - _token["at"] < 2400:
        return _token["v"]
    try:
        out = subprocess.run(
            "gcloud auth print-identity-token",
            shell=True, capture_output=True, text=True, timeout=30,
        )
        tok = (out.stdout or "").strip()
        if not tok:
            sys.stderr.write("[token] gcloud 실패: " + (out.stderr or "")[:200] + "\n")
            return None
        _token.update(v=tok, at=now)
        return tok
    except Exception as e:
        sys.stderr.write(f"[token] 예외: {e}\n")
        return None


def _user_headers(token):
    return {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "X-User-Id": "local-tester",
        "X-User-Name": quote("로컬테스터"),
        "X-User-Role": "tester",
        "X-User-Permissions": "manage_kb",
    }


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>의료 RAG 테스트</title>
<style>
 body{font-family:system-ui,'Malgun Gothic',sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#1c1c1c}
 h1{font-size:18px} .sub{color:#888;font-size:12px;margin-bottom:16px}
 #log{border:1px solid #ddd;border-radius:8px;padding:12px;min-height:280px;white-space:pre-wrap;line-height:1.5}
 .u{color:#0a58ca;font-weight:600;margin-top:10px}
 .a{color:#111;margin:4px 0 10px}
 .meta{color:#888;font-size:12px}
 .row{display:flex;gap:8px;margin-top:12px}
 textarea{flex:1;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:14px;resize:vertical}
 button{padding:10px 18px;border:0;border-radius:8px;background:#0a58ca;color:#fff;font-size:14px;cursor:pointer}
 button:disabled{background:#9bb8e6}
</style></head><body>
<h1>의료 RAG 테스트 (dev)</h1>
<div class="sub">브라우저 → 로컬 프록시 → 클라우드 RAG. 질문을 입력하세요. (대화는 멀티턴 유지)</div>
<div id="log"></div>
<div class="row">
 <textarea id="q" rows="2" placeholder="예: 두통이 3일째 있어요"></textarea>
 <button id="send" onclick="ask()">보내기</button>
</div>
<script>
const conv = crypto.randomUUID();
const log = document.getElementById('log');
function add(html){ const d=document.createElement('div'); d.innerHTML=html; log.appendChild(d); log.scrollTop=log.scrollHeight; return d; }
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q) return;
  const btn=document.getElementById('send'); btn.disabled=true;
  add('<div class="u">🙋 '+q+'</div>');
  document.getElementById('q').value='';
  const ans=add('<div class="a">…</div>'); let text=''; let meta='';
  try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({query:q,conversation_id:conv})});
    const reader=res.body.getReader(); const dec=new TextDecoder(); let buf='';
    while(true){ const {value,done}=await reader.read(); if(done) break;
      buf+=dec.decode(value,{stream:true}); let i;
      while((i=buf.indexOf('\\n\\n'))>=0){ const line=buf.slice(0,i); buf=buf.slice(i+2);
        const m=line.match(/^data: (.*)$/s); if(!m) continue; let ev; try{ev=JSON.parse(m[1]);}catch(e){continue;}
        if(ev.type==='GENERATION'){ text+=(ev.text||''); ans.innerHTML='<div class="a">'+text.replace(/</g,'&lt;')+'</div>'; }
        else if(ev.type==='EVIDENCE_CHECK'){ meta='근거: '+(ev.data&&ev.data.quality)+' / '+(ev.data&&ev.data.decision); }
        else if(ev.type==='INFO'&&ev.data&&ev.data.search_results){ meta='검색결과 '+ev.data.search_results.length+'건 · '+meta; }
        else if(ev.type==='STOP'){ const c=(ev.citations||[]).length; if(c) meta+=' · 인용 '+c+'개'; }
        else if(ev.type==='ERROR'){ text+='\\n[오류] '+(ev.message||''); ans.innerHTML='<div class="a">'+text+'</div>'; }
        log.scrollTop=log.scrollHeight;
      }
    }
    if(meta) add('<div class="meta">'+meta+'</div>');
    if(!text) ans.innerHTML='<div class="a">(빈 응답 — 검색 결과 부족일 수 있음)</div>';
  }catch(e){ ans.innerHTML='<div class="a">[요청 실패] '+e+'</div>'; }
  btn.disabled=false;
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask();}});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    rag_url = DEFAULT_RAG_URL

    def log_message(self, *a):
        pass  # 콘솔 조용히

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/chat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        payload = self.rfile.read(length) if length else b"{}"
        self._proxy_chat(payload, retry=True)

    def _proxy_chat(self, payload, retry):
        token = get_id_token()
        if not token:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'data: {"type":"ERROR","message":"gcloud \xed\x86\xa0\xed\x81\xb0 \xeb\xb0\x9c\xea\xb8\x89 \xec\x8b\xa4\xed\x8c\xa8 \xe2\x80\x94 gcloud \xeb\xa1\x9c\xea\xb7\xb8\xec\x9d\xb8 \xed\x99\x95\xec\x9d\xb8"}\n\n')
            return
        req = urllib.request.Request(
            self.rag_url + "/api/rag/chat", data=payload,
            headers=_user_headers(token), method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and retry:
                get_id_token(force=True)
                return self._proxy_chat(payload, retry=False)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            msg = json.dumps({"type": "ERROR", "message": f"클라우드 {e.code}: 인증/요청 오류"}, ensure_ascii=False)
            self.wfile.write(("data: " + msg + "\n\n").encode("utf-8"))
            return
        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            msg = json.dumps({"type": "ERROR", "message": f"연결 오류: {e}"}, ensure_ascii=False)
            self.wfile.write(("data: " + msg + "\n\n").encode("utf-8"))
            return
        # SSE 패스스루
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--rag-url", default=DEFAULT_RAG_URL)
    args = ap.parse_args()
    Handler.rag_url = args.rag_url.rstrip("/")

    tok = get_id_token()
    print("=" * 56)
    print(" 의료 RAG 로컬 테스트 UI")
    print(f"  대상   : {Handler.rag_url}")
    print(f"  토큰   : {'발급 OK' if tok else '실패(gcloud 로그인 확인)'}")
    print(f"  브라우저: http://localhost:{args.port}")
    print("  종료   : Ctrl+C")
    print("=" * 56)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료")


if __name__ == "__main__":
    main()
