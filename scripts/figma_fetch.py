# -*- coding: utf-8 -*-
"""
Figma REST API 리더 — MCP 좌석 호출한도 우회용 (읽기 전용).

인증: 개인 액세스 토큰(File content: Read-only 스코프)을 환경변수 FIGMA_TOKEN
또는 리포 루트 .env(FIGMA_TOKEN=...)에 둔다. 토큰은 커밋/채팅 금지(.env는 gitignore).

사용:
    python scripts/figma_fetch.py pages  <fileKey|URL>
    python scripts/figma_fetch.py tree   <fileKey|URL> [nodeId] [--depth 3]
    python scripts/figma_fetch.py dump   <fileKey|URL> <nodeId> [--out FILE]
    python scripts/figma_fetch.py render <fileKey|URL> <nodeId...> [--scale 2] [--out DIR]

nodeId 는 "24973:61891" / "24973-61891" / node-id 포함 URL 모두 허용.
render 결과 PNG 는 기본 docs/design/figma/ (리포 .gitignore 가 *.png 제외라 커밋 안 됨).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from urllib.parse import urlsplit, parse_qs

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

try:
    import requests
except ImportError:
    print("requests 필요: pip install requests", file=sys.stderr)
    sys.exit(2)

# 사내 프록시 TLS 가로채기 대응 — OS(Windows) 인증서 저장소 사용.
# (S3 다운로드가 self-signed chain 으로 막히는 환경. 미설치 시 조용히 폴백.)
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_API = "https://api.figma.com/v1"
_TIMEOUT = 60
_RETRIES = 4


def _load_token() -> str:
    tok = os.environ.get("FIGMA_TOKEN", "").strip()
    if not tok:
        env_path = os.path.join(_REPO_ROOT, ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("FIGMA_TOKEN="):
                        tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not tok:
        print(
            "FIGMA_TOKEN 이 없습니다.\n"
            "  1) figma.com → 프로필 → Settings → Security → Personal access tokens\n"
            "  2) Generate new token — 스코프는 'File content: Read only' 만, 만료 30~90일 권장\n"
            "  3) 리포 루트 .env 에 한 줄 추가:  FIGMA_TOKEN=figd_로시작하는토큰\n"
            "  (토큰을 채팅/커밋에 붙이지 마세요 — .env 는 gitignore 됨)",
            file=sys.stderr,
        )
        sys.exit(1)
    return tok


def _file_key(arg: str) -> str:
    """fileKey 또는 figma.com URL → fileKey."""
    m = re.search(r"figma\.com/(?:design|file|board|slides)/([A-Za-z0-9]+)", arg)
    return m.group(1) if m else arg


def _node_id(arg: str) -> str:
    """'1:2' / '1-2' / node-id 쿼리 포함 URL → '1:2'."""
    if "figma.com" in arg:
        q = parse_qs(urlsplit(arg).query).get("node-id", [""])[0]
        arg = q or arg
    return arg.replace("-", ":")


def _get(token: str, path: str, params=None) -> dict:
    url = f"{_API}{path}"
    for attempt in range(_RETRIES):
        r = requests.get(url, params=params or {},
                         headers={"X-Figma-Token": token}, timeout=_TIMEOUT)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "0") or 0) or (2 ** attempt * 5)
            print(f"[rate-limit] {wait}s 대기 후 재시도...", file=sys.stderr)
            time.sleep(wait)
            continue
        if r.status_code == 403:
            sys.exit("403 — 토큰 스코프(File content read) 또는 파일 접근 권한을 확인하세요. "
                     "조직 파일이 막히면 드래프트 복사본 fileKey 로 시도.")
        if r.status_code == 404:
            sys.exit("404 — fileKey/nodeId 확인 (드래프트 복사본 키를 쓰고 있는지도).")
        r.raise_for_status()
        return r.json()
    sys.exit("rate limit 재시도 초과 — 잠시 후 다시 실행하세요.")


def _walk(node: dict, depth: int, max_depth: int, lines: list) -> None:
    box = node.get("absoluteBoundingBox") or {}
    size = f" {round(box.get('width', 0))}x{round(box.get('height', 0))}" if box else ""
    lines.append("  " * depth + f"[{node.get('type','?')}] {node.get('name','')!r} "
                 f"id={node.get('id','')}{size}")
    if depth < max_depth:
        for ch in node.get("children", []) or []:
            _walk(ch, depth + 1, max_depth, lines)


def cmd_pages(token: str, key: str) -> None:
    doc = _get(token, f"/files/{key}", {"depth": 1})
    print(f"파일: {doc.get('name')}  (lastModified {doc.get('lastModified')})")
    for page in doc["document"].get("children", []):
        print(f"  page {page['id']}  {page['name']!r}")


def cmd_tree(token: str, key: str, node: str | None, depth: int) -> None:
    lines: list = []
    if node:
        data = _get(token, f"/files/{key}/nodes", {"ids": node, "depth": depth})
        for nid, entry in data.get("nodes", {}).items():
            _walk(entry["document"], 0, depth, lines)
    else:
        doc = _get(token, f"/files/{key}", {"depth": min(depth, 2)})
        _walk(doc["document"], 0, depth, lines)
    print("\n".join(lines))


def cmd_dump(token: str, key: str, node: str, out: str | None) -> None:
    data = _get(token, f"/files/{key}/nodes", {"ids": node})
    out = out or os.path.join(_REPO_ROOT, "docs", "design", "figma",
                              f"node-{node.replace(':', '-')}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"저장: {out}  ({os.path.getsize(out):,} bytes)")


def cmd_texts(token: str, key: str, node: str, max_chars: int) -> None:
    """노드 서브트리의 TEXT 레이어를 프레임별로 묶어 출력 — 렌더 불가/스로틀 시 우회.

    이미지 렌더(/v1/images)와 달리 /v1/files/:key/nodes 는 별도 경로라
    렌더 스로틀에 안 걸린다. 화면 문구·버튼 라벨·상태 메시지 분석용.
    """
    data = _get(token, f"/files/{key}/nodes", {"ids": node})
    printed = 0

    def walk(n, frame_name):
        nonlocal printed
        if printed >= max_chars:
            return
        t = n.get("type")
        name = (n.get("name") or "").strip()
        if t == "FRAME" and name and name != "-":
            frame_name = name
            line = f"\n## {name}"
            print(line)
            printed += len(line)
        elif t == "SECTION" and name:
            line = f"\n# [{name}]"
            print(line)
            printed += len(line)
        if t == "TEXT":
            chars = (n.get("characters") or "").strip()
            if chars:
                line = "  " + chars.replace("\n", " / ")[:300]
                print(line)
                printed += len(line)
        for ch in n.get("children", []) or []:
            walk(ch, frame_name)

    for nid, entry in (data.get("nodes") or {}).items():
        walk(entry["document"], "")
    if printed >= max_chars:
        print(f"\n... (출력 상한 {max_chars}자 도달 — --max-chars 로 조절)")


def cmd_render(token: str, key: str, nodes: list, scale: float, out_dir: str) -> None:
    ids = ",".join(nodes)
    data = _get(token, f"/images/{key}", {"ids": ids, "format": "png", "scale": scale})
    if data.get("err"):
        sys.exit(f"렌더 실패: {data['err']}")
    os.makedirs(out_dir, exist_ok=True)
    for nid, url in (data.get("images") or {}).items():
        if not url:
            print(f"  {nid}: 렌더 불가(빈 URL)", file=sys.stderr)
            continue
        png = requests.get(url, timeout=_TIMEOUT)
        png.raise_for_status()
        path = os.path.join(out_dir, f"{nid.replace(':', '-')}@{scale}x.png")
        with open(path, "wb") as f:
            f.write(png.content)
        print(f"저장: {path}  ({len(png.content):,} bytes)")


def main() -> None:
    p = argparse.ArgumentParser(description="Figma REST 리더 (읽기 전용)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("pages");  sp.add_argument("file")
    st = sub.add_parser("tree");   st.add_argument("file"); st.add_argument("node", nargs="?")
    st.add_argument("--depth", type=int, default=3)
    sd = sub.add_parser("dump");   sd.add_argument("file"); sd.add_argument("node")
    sd.add_argument("--out")
    sx = sub.add_parser("texts");  sx.add_argument("file"); sx.add_argument("node")
    sx.add_argument("--max-chars", type=int, default=20000)
    sr = sub.add_parser("render"); sr.add_argument("file"); sr.add_argument("nodes", nargs="+")
    sr.add_argument("--scale", type=float, default=2)
    sr.add_argument("--out", default=os.path.join(_REPO_ROOT, "docs", "design", "figma"))

    a = p.parse_args()
    token = _load_token()
    key = _file_key(a.file)
    if a.cmd == "pages":
        cmd_pages(token, key)
    elif a.cmd == "tree":
        cmd_tree(token, key, _node_id(a.node) if a.node else None, a.depth)
    elif a.cmd == "dump":
        cmd_dump(token, key, _node_id(a.node), a.out)
    elif a.cmd == "texts":
        cmd_texts(token, key, _node_id(a.node), a.max_chars)
    elif a.cmd == "render":
        cmd_render(token, key, [_node_id(n) for n in a.nodes], a.scale, a.out)


if __name__ == "__main__":
    main()
