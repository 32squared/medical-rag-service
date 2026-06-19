"""
Collection Health — 수집 건전성 평가 (07-revised-plan.md §4-4).

자동 수집은 출처 사이트 개편·IP 차단(예: MFDS NAT IP 미등록)으로 *조용히*
0건을 반환하기 쉽다. 이 모듈은 출처별 수집량을 보고 0건/급감을 경고로 표면화한다.

순수 함수 — DB/네트워크 없이 테스트 가능. collect_public_kb.collect_all이 호출.
"""

from __future__ import annotations

from typing import Dict, List, Optional


def assess_collection_health(
    counts: Dict[str, int],
    baseline: Optional[Dict[str, int]] = None,
    drop_threshold: float = 0.5,
    expected_sources: Optional[List[str]] = None,
) -> Dict:
    """수집 결과 건전성 평가.

    Args:
        counts: {source_id: 이번 수집 건수}
        baseline: {source_id: 직전 수집 건수}(선택) — 급감 판정용
        drop_threshold: baseline 대비 이 비율 미만이면 'low'(기본 0.5 = 절반)
        expected_sources: 수집을 기대한 출처 목록(누락/0건이면 'empty'). 미지정 시 counts 키 사용.

    Returns:
        {"status": {src: 'ok'|'empty'|'low'}, "warnings": [str], "healthy": bool}
    """
    sources = expected_sources if expected_sources is not None else list(counts.keys())
    status: Dict[str, str] = {}
    warnings: List[str] = []

    for src in sources:
        cnt = int(counts.get(src, 0) or 0)
        if cnt == 0:
            status[src] = "empty"
            warnings.append(
                f"[{src}] 수집 0건 — 출처 차단/사이트 개편/키 누락 가능. 점검 필요."
            )
            continue
        if baseline:
            prev = int(baseline.get(src, 0) or 0)
            if prev > 0 and cnt < prev * drop_threshold:
                status[src] = "low"
                warnings.append(
                    f"[{src}] 수집 급감 {prev}→{cnt}건 (<{int(drop_threshold*100)}%) — 스크래핑 손상 의심."
                )
                continue
        status[src] = "ok"

    healthy = all(s == "ok" for s in status.values()) if status else True
    return {"status": status, "warnings": warnings, "healthy": healthy}
