"""
personal_context.py — findings → 사용자 답변용 "내 기록 참고" 블록 (개인화 P1a, 경계선 ③ 렌더).

정본: docs/plan/14-personalization-consolidated.md §6 C19, 09 §7(주입 레이어), 13 §1.

규율:
- [관련성 게이트] 질의 scope와 매칭되는 finding만 표면화(09 §7-1). 매칭 0 → 빈 블록(개인화 생략·과노출 차단).
- [I1] 원시 측정값 미노출 — findings는 이미 라벨만 보유(vital_rules).
- [I12] 사용자 라벨 중립 3단만. 임상/질환 라벨(clinical_label) 미사용 → 개인귀속 진단 0.
- [측정시점] '최근 측정' 프레이밍 + 의료진 상담 위임(진단 단정 0).
- 실제 [R#] 인용 마커는 wiring(chunks 동반적재 후 위치 부여)에서 삽입 — 본 렌더는 cite_doc_ids를 반환만.

build()는 순수 함수 — DB/LLM 불필요. 단위테스트 가능.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# 질의 scope 키워드 → signal_key (관련성 게이트). 질의에 키워드가 있어야 해당 finding 표면화.
_SCOPE_KEYWORDS: Dict[str, List[str]] = {
    "blood_pressure": ["혈압", "고혈압", "저혈압", "수축기", "이완기", "어지럼", "현기증", "두통"],
    "heart_rate": ["맥박", "심박", "심장", "두근", "빈맥", "서맥", "부정맥"],
    "spo2": ["산소", "산소포화도", "호흡", "숨", "숨참", "기침", "가래"],
    "body_temperature": ["열", "발열", "체온", "미열", "오한", "고열"],
    "bmi": ["체중", "비만", "몸무게", "체질량", "살", "비만도"],
    "fasting_glucose": ["혈당", "당뇨", "공복혈당", "당화"],
    "hba1c": ["당화혈색소", "당뇨", "혈당", "당화"],
    # 환경(5층) — 호흡기·알레르기·공기 관련 질의에서만 환기 노트 표면화
    "air_quality": ["기침", "가래", "숨", "호흡", "답답", "콧물", "재채기", "코막힘",
                    "알레르기", "천식", "공기", "환기", "미세먼지", "먼지", "목"],
}

# signal_key → 사용자 표시명
_SIGNAL_DISPLAY = {
    "blood_pressure": "혈압",
    "heart_rate": "심박수",
    "spo2": "산소포화도",
    "body_temperature": "체온",
    "bmi": "체질량지수",
    "fasting_glucose": "공복혈당",
    "hba1c": "당화혈색소",
    "air_quality": "실내 공기질",
}

# 중립 라벨(I12) → 사용자 문구. 질환명·원시값 없음.
_LABEL_PHRASE = {
    "안정": "현재 측정 기준으로는 특이소견이 보이지 않습니다",
    "주의": "관리가 권장되는 구간으로 확인됩니다",
    "경고": "기준을 벗어난 구간으로, 의료진 확인이 권장됩니다",
}

_BLOCK_HEADER = "## 📋 내 기록 참고"
_BLOCK_CLOSING = "측정값의 해석과 진단은 의료진과 상담하세요."


def relevance_gate(query: Optional[str], findings: List[Dict]) -> List[Dict]:
    """질의 scope와 매칭되는 finding만 통과(09 §7-1). 매칭 0이면 빈 리스트(과노출 차단)."""
    q = query or ""
    kept = []
    for f in findings:
        sig = f.get("signal_key")
        if f.get("label_user") not in _LABEL_PHRASE:
            continue  # 라벨 없는(no_match/denied) finding은 표면화 안 함
        keywords = _SCOPE_KEYWORDS.get(sig, [])
        if any(kw in q for kw in keywords):
            kept.append(f)
    return kept


def _relevant_combos(query: Optional[str], findings: List[Dict]) -> List[Dict]:
    """교차신호 화이트리스트 조합(I9) 중, 질의 scope가 조합 신호 하나라도 건드리는 것만."""
    try:
        from vital_rules import match_cross_signals
    except Exception:
        return []
    combos = match_cross_signals(findings)
    q = query or ""
    out = []
    for c in combos:
        if any(any(kw in q for kw in _SCOPE_KEYWORDS.get(s, [])) for s in c.get("signals", [])):
            out.append(c)
    return out


def build(findings: List[Dict], query: Optional[str]) -> Dict:
    """findings → 관련성 게이트 통과분의 "내 기록 참고" 블록(밴드 + 교차신호 조합).

    Returns:
        {
          "surfaced":     [{signal_key|combo_id, label_user?, cite_doc_id, sentence}, ...],
          "cite_doc_ids": [unique cite_doc_id ...],   # wiring이 chunks에 동반적재(11 §5)
          "block_md":     str,                         # 프리뷰(실제 [R#] 마커는 wiring에서 삽입)
        }
    빈 블록(매칭 0)이면 block_md="" — 개인화 생략.
    """
    findings = findings or []
    surfaced_in = relevance_gate(query, findings)
    combos = _relevant_combos(query, findings)
    if not surfaced_in and not combos:
        return {"surfaced": [], "cite_doc_ids": [], "block_md": ""}

    surfaced: List[Dict] = []
    cite_ids: List[str] = []
    lines = [_BLOCK_HEADER]

    # 밴드 finding (환경 등 자체 sentence 보유 finding은 그대로 사용)
    for f in surfaced_in:
        sentence = f.get("sentence")
        if not sentence:
            display = _SIGNAL_DISPLAY.get(f["signal_key"], f["signal_key"])
            phrase = _LABEL_PHRASE[f["label_user"]]
            sentence = f"최근 측정된 {display}은(는) {phrase}"
        lines.append(f"- {sentence}.")
        surfaced.append({
            "signal_key": f["signal_key"],
            "label_user": f["label_user"],
            "cite_doc_id": f.get("cite_doc_id"),
            "sentence": sentence,
        })
        cid = f.get("cite_doc_id")
        if cid and cid not in cite_ids:
            cite_ids.append(cid)

    # 교차신호 조합 (화이트리스트·관련성 통과분)
    for c in combos:
        sentence = c.get("text", "")
        lines.append(f"- {sentence}.")
        surfaced.append({
            "combo_id": c.get("combo_id"),
            "signals": c.get("signals"),
            "cite_doc_id": c.get("cite_doc_id"),
            "sentence": sentence,
        })
        cid = c.get("cite_doc_id")
        if cid and cid not in cite_ids:
            cite_ids.append(cid)

    lines.append("")
    lines.append(_BLOCK_CLOSING)

    return {
        "surfaced": surfaced,
        "cite_doc_ids": cite_ids,
        "block_md": "\n".join(lines),
    }


def safe_block(findings: List[Dict], query: Optional[str]) -> str:
    """build() + C20 백스톱을 묶어 **주입 가능한 안전 블록 문자열**만 반환.

    배선(generate_response)이 그대로 답변에 후append할 수 있는 형태.
    빈 블록(관련성 게이트 0) 또는 C20 안전 위반 → "" (fail-closed, 주입 안 함).
    개인 데이터는 LLM 프롬프트에 미투입 — 이 블록은 생성 후 답변에 결정적으로 덧붙는다.
    """
    out = build(findings or [], query)
    block_md = out.get("block_md") or ""
    if not block_md:
        return ""
    try:
        from personalization_safety import assert_personal_block_safe
        assert_personal_block_safe(block_md)
    except Exception:
        return ""  # 안전 위반 → 주입하지 않음(fail-closed)
    return block_md
