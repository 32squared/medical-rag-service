"""
kb_collect.clients — 접근 방식별 클라이언트 (공공데이터포털 OpenAPI · HTML · 파일).

공통: 재시도·백오프·요청 간격, 사용자 에이전트, 체크섬. requests 는 지연 import.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.robotparser
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

USER_AGENT = "medical-rag-kb-collector/1.0 (+public health info KB; contact: ops)"
_TIMEOUT = 30
_RETRY = 3
_BACKOFF = 1.5
_RATE_SLEEP = 1.0


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Base:
    def __init__(self, session=None, rate_sleep: float = _RATE_SLEEP):
        self._session = session
        self._rate_sleep = rate_sleep
        self._last = 0.0

    @property
    def session(self):
        if self._session is None:
            import requests  # 지연 import
            s = requests.Session()
            s.headers.update({"User-Agent": USER_AGENT})
            self._session = s
        return self._session

    def _throttle(self):
        wait = self._rate_sleep - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def _request(self, method: str, url: str, **kw):
        last_err = None
        for attempt in range(_RETRY):
            self._throttle()
            try:
                resp = self.session.request(method, url, timeout=_TIMEOUT, **kw)
                if resp.status_code >= 500:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                return resp
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(_BACKOFF ** attempt)
        raise RuntimeError(f"{method} {url} 실패: {last_err}")


class DataGoKrClient(_Base):
    """
    공공데이터포털(apis.data.go.kr) 목록형 API 공용 클라이언트.
    - serviceKey + pageNo/numOfRows 페이징, JSON(type=json) 우선, XML 폴백
    - resultCode != 00 이면 resultMsg 로 예외(서비스키 미등록 등을 조용히 0건으로 만들지 않음)
    """

    def __init__(self, service_key: str, session=None):
        super().__init__(session)
        if not service_key:
            raise ValueError("DATA_GO_KR_KEY 가 비어 있다")
        self.key = service_key

    def iter_items(self, url: str, params: Optional[Dict[str, Any]] = None,
                   page_size: int = 100, max_items: int = 1000,
                   items_path: Optional[List[str]] = None) -> Iterator[Dict]:
        items_path = items_path or ["response", "body", "items", "item"]
        page = 1
        yielded = 0
        while yielded < max_items:
            q = dict(params or {})
            q.update({"serviceKey": self.key, "pageNo": page, "numOfRows": page_size, "type": "json"})
            resp = self._request("GET", url, params=q)
            data = self._parse(resp)
            header = (data.get("response") or {}).get("header") or {}
            code = str(header.get("resultCode", "00"))
            if code not in ("00", "0"):
                raise RuntimeError(f"data.go.kr 오류 {code}: {header.get('resultMsg')}")
            items = _dig(data, items_path)
            if items is None:
                items = []
            if isinstance(items, dict):
                items = [items]
            if not items:
                break
            for it in items:
                yield it
                yielded += 1
                if yielded >= max_items:
                    break
            total = _dig(data, ["response", "body", "totalCount"])
            if total is not None and page * page_size >= int(total):
                break
            page += 1

    @staticmethod
    def _parse(resp) -> Dict:
        text = resp.text or ""
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "json" in ctype or text.lstrip().startswith("{"):
            return json.loads(text)
        return _xml_to_dict(text)


class HtmlClient(_Base):
    """HTML 수집 — robots.txt 를 호스트별로 한 번 읽어 허용되지 않으면 예외."""

    def __init__(self, session=None, respect_robots: bool = True):
        super().__init__(session)
        self.respect_robots = respect_robots
        self._robots: Dict[str, urllib.robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        host = urlparse(url).netloc
        rp = self._robots.get(host)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self.session.get(f"https://{host}/robots.txt", timeout=_TIMEOUT)
                rp.parse((resp.text or "").splitlines() if resp.status_code == 200 else [])
            except Exception:  # noqa: BLE001
                rp.parse([])
            self._robots[host] = rp
        return rp.can_fetch(USER_AGENT, url) and rp.can_fetch("*", url)

    def get_text(self, url: str, **kw) -> str:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt 가 수집을 허용하지 않음: {url}")
        resp = self._request("GET", url, **kw)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {url}")
        return resp.text


class FileClient(_Base):
    """파일(CSV/JSON/XLSX/PDF) 내려받기 — 바이트와 체크섬."""

    def download(self, url: str) -> Dict[str, Any]:
        resp = self._request("GET", url)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {url}")
        data = resp.content
        return {"bytes": data, "checksum": hashlib.sha256(data).hexdigest(),
                "fetched_at": now_iso(), "content_type": resp.headers.get("Content-Type", "")}


def _dig(d: Any, path: List[str]):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _xml_to_dict(text: str) -> Dict:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text)

    def conv(el):
        kids = list(el)
        if not kids:
            return el.text
        out: Dict[str, Any] = {}
        for k in kids:
            v = conv(k)
            if k.tag in out:
                if not isinstance(out[k.tag], list):
                    out[k.tag] = [out[k.tag]]
                out[k.tag].append(v)
            else:
                out[k.tag] = v
        return out

    return {root.tag: conv(root)}
