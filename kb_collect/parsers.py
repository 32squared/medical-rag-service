"""
kb_collect.parsers — 레코드 → KB 문서(dict) 변환. 순수 함수(네트워크·DB 없음).

문서 dict 규격(collect_public_kb 와 동일):
  {title, content_md, source_url, source_checksum, source_fetched_at, published_at?}
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .clients import now_iso, sha256

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    t = _TAG_RE.sub(" ", str(text))
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = _WS_RE.sub(" ", t)
    return "\n".join(line.strip() for line in t.splitlines() if line.strip())


def records_to_documents(
    records: Iterable[Dict],
    *,
    title_field: str,
    body_fields: Sequence[Tuple[str, str]],
    url_template: str,
    id_field: str,
    institution: str,
    disclaimer: str = "",
    published_field: Optional[str] = None,
    title_prefix: str = "",
) -> List[Dict]:
    """
    목록형 API 레코드를 절(section)별 마크다운 문서로 바꾼다.
      body_fields: [(절 제목, 레코드 필드), ...] — 값이 비면 절을 생략
      url_template: "https://…/{itemSeq}" 처럼 레코드 필드로 포맷
    원문을 고쳐 쓰지 않는다(HTML 태그 제거·공백 정리만).
    """
    docs: List[Dict] = []
    fetched = now_iso()
    for r in records:
        title = strip_html(r.get(title_field))
        if not title:
            continue
        sections = []
        for heading, field in body_fields:
            val = strip_html(r.get(field))
            if val:
                sections.append(f"## {heading}\n\n{val}")
        if not sections:
            continue
        body = "\n\n".join(sections)
        md = f"# {title_prefix}{title}\n\n출처: {institution}\n\n{body}"
        if disclaimer:
            md += f"\n\n{disclaimer}"
        try:
            url = url_template.format(**{k: (r.get(k) or "") for k in _fields_in(url_template)})
        except Exception:  # noqa: BLE001
            url = url_template
        docs.append({
            "title": f"{title_prefix}{title}",
            "content_md": md,
            "source_url": url,
            "source_checksum": sha256(md),
            "source_fetched_at": fetched,
            "published_at": r.get(published_field) if published_field else None,
            "external_id": str(r.get(id_field) or ""),
        })
    return docs


def _fields_in(template: str) -> List[str]:
    return re.findall(r"\{([a-zA-Z0-9_]+)\}", template)
