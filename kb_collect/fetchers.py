"""
kb_collect.fetchers — 카탈로그 항목의 `fetcher` 이름 → 함수.

규약: fetch(entry, max_items, env, clients) -> List[doc dict]
  기존 수집기(collect_public_kb·dur_collector)는 여기서 감싸고, 새 OpenAPI 출처는
  `datagokr_generic` 에 카탈로그의 `api` 설정(엔드포인트·필드 매핑)만 주면 된다.
아직 구현되지 않은 후보(cancer_go_kr 등)는 NotImplementedError 를 내고 runner 가
'not_implemented' 로 기록한다 — 조용히 0건이 되지 않게.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List

from .clients import DataGoKrClient
from .parsers import records_to_documents

Fetcher = Callable[[Dict, int, Dict, Dict], List[Dict]]
_REGISTRY: Dict[str, Fetcher] = {}


def register(name: str):
    def deco(fn: Fetcher) -> Fetcher:
        _REGISTRY[name] = fn
        return fn
    return deco


def get(name: str) -> Fetcher:
    if name not in _REGISTRY:
        raise KeyError(f"fetcher 미등록: {name}")
    return _REGISTRY[name]


def names() -> List[str]:
    return sorted(_REGISTRY)


# ── 기존 수집기 래핑 ─────────────────────────────────────────

@register("health_kdca")
def _health_kdca(entry, max_items, env, clients):
    import collect_public_kb as cpk
    return cpk.fetch_health_kdca(limit=max_items)


@register("nemc")
def _nemc(entry, max_items, env, clients):
    import collect_public_kb as cpk
    return cpk.fetch_nemc_first_aid()[:max_items]


@register("mfds_safety_letters")
def _mfds_letters(entry, max_items, env, clients):
    import collect_public_kb as cpk
    return cpk.fetch_mfds_safety_letters(limit=max_items)


@register("mfds_drug_info")
def _mfds_drug_info(entry, max_items, env, clients):
    import collect_public_kb as cpk
    return cpk.fetch_mfds_drug_info(api_key=env.get(entry["key_env"], ""), limit=max_items)


@register("kdca_api")
def _kdca_api(entry, max_items, env, clients):
    import collect_public_kb as cpk
    return cpk.fetch_kdca_openapi(api_key=env.get(entry["key_env"], ""), limit=max_items)


@register("shortlist")
def _shortlist(entry, max_items, env, clients):
    import collect_public_kb as cpk
    return cpk.fetch_shortlist(limit_per_seed=max_items)


@register("mfds_dur")
def _mfds_dur(entry, max_items, env, clients):
    from dur_collector import collect_dur
    from seed_dur import build_dur_documents
    raw = collect_dur(env.get(entry["key_env"], ""))
    docs = build_dur_documents(raw)
    return docs[:max_items]


# ── 범용 OpenAPI 수집기 — 카탈로그 entry["api"] 로 구동 ──────────

@register("datagokr_generic")
def _datagokr_generic(entry, max_items, env, clients):
    """
    entry["api"] = {
      "url": "https://apis.data.go.kr/…/getList",
      "params": {...},                    # serviceKey·페이징 외 고정 파라미터
      "items_path": ["response","body","items","item"],   # 선택
      "title_field": "itemName",
      "body_fields": [["효능", "efcyQesitm"], ...],
      "url_template": "https://…/{itemSeq}",
      "id_field": "itemSeq",
      "published_field": "updateDe",      # 선택
      "disclaimer": "…",                  # 선택
      "title_prefix": "",                 # 선택
    }
    """
    api = entry.get("api")
    if not api or not api.get("url") or not api.get("title_field"):
        raise NotImplementedError(f"{entry['id']}: 카탈로그 api 설정(url·필드 매핑)이 아직 없다 — 키 발급 뒤 상세기능 확인")
    client = clients.get("datagokr") or DataGoKrClient(env.get(entry["key_env"], ""))
    records = client.iter_items(api["url"], params=api.get("params"), max_items=max_items,
                                items_path=api.get("items_path"))
    return records_to_documents(
        records,
        title_field=api["title_field"],
        body_fields=[tuple(x) for x in api["body_fields"]],
        url_template=api["url_template"],
        id_field=api["id_field"],
        institution=entry["institution"],
        disclaimer=api.get("disclaimer", ""),
        published_field=api.get("published_field"),
        title_prefix=api.get("title_prefix", ""),
    )


# ── 아직 구현 전인 후보 ───────────────────────────────────────

def _not_implemented(name: str) -> Fetcher:
    def fn(entry, max_items, env, clients):
        raise NotImplementedError(f"{name}: 접근 방법 확인 뒤 구현")
    return fn


for _n in ("law_drf_notice", "foodsafety_generic", "cancer_go_kr", "nhis_health_in", "kdca_press", "kdca_nip"):
    _REGISTRY[_n] = _not_implemented(_n)
