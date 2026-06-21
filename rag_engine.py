"""
RAG 검색 엔진 — Hybrid Search + Medical Safety Boost
Phase 1 MVP: pgvector cosine + tsvector BM25, RRF fusion

핵심 함수:
  hybrid_search()          — 메인 진입점
  rrf_fusion()             — Reciprocal Rank Fusion (k=60)
  detect_symptom_keys()    — 질의 → symptom_key 추출
  apply_red_flag_boost()   — red_flag ×1.3, emergency ×1.2
  check_evidence_topic_alignment() — 양현종 자문 반영 (무관 청크 차단)
  apply_country_boost()    — KR ×1.15, regulatory_korea ×1.1

T5 추가 (generate_response):
  generate_response()      — Hybrid search → 프롬프트 → LLM 스트리밍 → 가드레일 → DB 기록
  _build_rag_system_prompt()   — 4단 응답 구조 강제 시스템 프롬프트
  _build_rag_user_prompt()     — 인용 번호 부여 사용자 프롬프트
  _regenerate_with_warning()   — HIGH 위반 시 gpt-5-mini 재생성
  _validate_and_fix_citations() — 인용 번호 검증
  _ensure_disclaimer()          — 면책조항 자동 부착
  _ensure_four_section_structure() — 4단 응답 구조 헤더 검증
  _detect_emergency_signal()    — 응급 신호 감지
  _get_conversation_state()     — rag_conversation_state.emergency_state 조회(rag_db 위임)
  _set_conversation_state()     — rag_conversation_state.emergency_state 갱신(rag_db 위임)
  _build_emergency_response()   — EMERGENCY_REDIRECTED 고정 응답
  _extract_citations()          — [N] 인용 마커 → chunk_id 매핑
  _insert_rag_query()           — rag_queries INSERT
  _format_search_result()       — INFO 이벤트용 청크 직렬화

SQLite 모드에서는 NotImplementedError 발생 (RAG requires PostgreSQL + pgvector).
"""
import os
import re
import json
import time
import uuid
import logging
from typing import List, Optional, Iterator, Dict

logger = logging.getLogger(__name__)

# ─── Phase A: Retrieval Gate 환경변수 (shadow mode 기본값) ────────────────────
# RETRIEVAL_GATE_ENFORCE=false(기본): 게이트 결과를 로깅만 하고 응답은 정상 진행.
# RETRIEVAL_GATE_ENFORCE=true: INSUFFICIENT 판정 시 LLM 호출을 스킵하고 템플릿 반환.
RETRIEVAL_GATE_ENFORCE = os.environ.get("RETRIEVAL_GATE_ENFORCE", "false").lower() == "true"
GATE_TOP1_PASS = float(os.environ.get("GATE_TOP1_PASS", "0.55"))
GATE_TOP1_WEAK = float(os.environ.get("GATE_TOP1_WEAK", "0.42"))
GATE_CHUNK_COUNT_PASS = int(os.environ.get("GATE_CHUNK_COUNT_PASS", "3"))
GATE_TOPIC_MATCH_PASS = int(os.environ.get("GATE_TOPIC_MATCH_PASS", "2"))
GATE_WEIGHTED_PASS = float(os.environ.get("GATE_WEIGHTED_PASS", "2.0"))
GATE_TOPIC_THRESHOLD = float(os.environ.get("GATE_TOPIC_THRESHOLD", "0.30"))
# evidence_topic 라벨링된 청크에만 적용하는 임계값 (미라벨링 청크는 자동 통과)
GATE_TOPIC_ALIGNMENT_THRESHOLD = float(os.environ.get("GATE_TOPIC_ALIGNMENT_THRESHOLD", "0.30"))
GATE_RELEVANT_COSINE = float(os.environ.get("GATE_RELEVANT_COSINE", "0.42"))
EVIDENCE_LEVEL_WEIGHT: Dict[str, float] = {"A": 1.0, "B": 0.7, "C": 0.4}

# ENABLE_EVIDENCE_TOPIC_CHECK=false: evidence_topic 정렬 검증 비활성화 (디버그/우회용)
# KB의 evidence_topic 컬럼이 비어있거나 임베딩 공간과 불일치할 때 임시 사용
ENABLE_EVIDENCE_TOPIC_CHECK = os.environ.get("ENABLE_EVIDENCE_TOPIC_CHECK", "true").lower() != "false"

# ─── 모듈 레벨 상수 ──────────────────────────────────────────
_DENSE_LIMIT = 20   # dense 검색 후보 수
_SPARSE_LIMIT = 20  # sparse 검색 후보 수
_RRF_K = 60         # RRF 파라미터

# ─── consultation_checklists.json 1회 로딩 ───────────────────
def _load_checklists() -> dict:
    """증상 카탈로그 → {"symptoms": {symptom_key: {...}}}.
    symptom_catalog 경유로 기존 42증상 + repo-local 보강(symptom_supplement)을 병합한다.
    실패 시 consultation_loader 직접 폴백(무손상)."""
    try:
        from symptom_catalog import load_catalog_by_symptom
        return load_catalog_by_symptom()
    except Exception:
        import consultation_loader
        return consultation_loader.load_checklists_by_symptom()


CHECKLISTS: dict = _load_checklists()

# ─── 임베딩 프로바이더 lazy singleton ────────────────────────
_embedding_provider_instance = None


def _get_embedding_provider():
    """get_embedding_provider('default') lazy singleton."""
    global _embedding_provider_instance
    if _embedding_provider_instance is None:
        from embedding_provider import get_embedding_provider
        _embedding_provider_instance = get_embedding_provider("default")
    return _embedding_provider_instance


# ─── SQLite 모드 감지 ─────────────────────────────────────────
def _is_postgres() -> bool:
    """dbcommon._use_postgres 플래그 참조."""
    try:
        import dbcommon as _db
        return _db._use_postgres
    except Exception:
        return False


def _require_postgres():
    """SQLite 모드이면 NotImplementedError 발생."""
    if not _is_postgres():
        raise NotImplementedError(
            "RAG features require PostgreSQL with pgvector. "
            "Set DATABASE_URL environment variable to enable. "
            "(SQLite mode does not support vector search)"
        )


# ════════════════════════════════════════════════════════════
#  Step A: Dense 검색 (pgvector cosine)
# ════════════════════════════════════════════════════════════
def _dense_search(
    query_embedding: List[float],
    source_types: Optional[List[str]],
    limit: int = _DENSE_LIMIT,
) -> List[dict]:
    """
    pgvector cosine 유사도 기반 dense 검색.

    Args:
        query_embedding: 질의 임베딩 벡터 (1536차원)
        source_types: source_id 필터 (None이면 전체)
        limit: 반환 최대 개수

    Returns:
        [{"chunk_id", "document_id", "content", "section_path",
          "symptom_tags", "severity", "evidence_country",
          "evidence_topic", "regulatory_korea", "topic_keywords",
          "source_id", "evidence_level", "title", "cosine_score"}, ...]
    """
    from dbcommon import get_conn, _p, _ph

    # pgvector 어댑터 등록
    try:
        from pgvector.psycopg2 import register_vector
        import psycopg2
    except ImportError:
        pass

    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    with get_conn() as (conn, cur):
        # pgvector register
        try:
            from pgvector.psycopg2 import register_vector
            register_vector(conn)
        except Exception:
            pass

        if source_types:
            ph_list = _ph(len(source_types))
            sql = f"""
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.content,
                    c.section_path,
                    c.symptom_tags,
                    c.severity,
                    c.evidence_country,
                    c.evidence_topic,
                    c.regulatory_korea,
                    c.topic_keywords,
                    d.source_id,
                    d.evidence_level,
                    d.title,
                    d.source_url,
                    1 - (c.embedding_primary <=> %s::vector(1536)) AS cosine_score
                FROM kb_chunks c
                JOIN kb_documents d ON c.document_id = d.id
                WHERE d.status = 'active'
                  AND d.source_id = ANY(ARRAY[{ph_list}]::text[])
                ORDER BY c.embedding_primary <=> %s::vector(1536)
                LIMIT %s
            """
            params = [vec_str] + source_types + [vec_str, limit]
        else:
            sql = f"""
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.content,
                    c.section_path,
                    c.symptom_tags,
                    c.severity,
                    c.evidence_country,
                    c.evidence_topic,
                    c.regulatory_korea,
                    c.topic_keywords,
                    d.source_id,
                    d.evidence_level,
                    d.title,
                    d.source_url,
                    1 - (c.embedding_primary <=> %s::vector(1536)) AS cosine_score
                FROM kb_chunks c
                JOIN kb_documents d ON c.document_id = d.id
                WHERE d.status = 'active'
                ORDER BY c.embedding_primary <=> %s::vector(1536)
                LIMIT %s
            """
            params = [vec_str, vec_str, limit]

        cur.execute(sql, params)
        rows = cur.fetchall()

    results = []
    for row in rows:
        r = dict(row)
        r["cosine_score"] = float(r.get("cosine_score") or 0.0)
        r["boost_reasons"] = []
        results.append(r)
    return results


# ════════════════════════════════════════════════════════════
#  Step B: Sparse 검색 (tsvector BM25)
# ════════════════════════════════════════════════════════════
import re as _re_kw

# 한국어 조사·어미 근사 제거 (어절 → 의미 토큰)
_KW_PARTICLE_RE = _re_kw.compile(
    r"(?:으로|에서|에게|까지|부터|이라고|라고|이며|하고|하며|되면|되어|이고|"
    r"이랑|랑|이나|한테|처럼|마다|밖에|"
    r"입니다|습니다|어요|아요|예요|네요|은|는|이|가|을|를|에|의|도|만|과|와|로|요|고|며|서|들|임|함)$"
)
_KW_STOP = {
    "것", "수", "등", "때", "더", "좀", "잘", "안", "못", "또", "그", "저", "거", "게", "걸",
    "점", "중", "및", "약간", "정도", "관련", "경우", "무엇", "어떻게", "어떤", "있는", "있어요",
    "있나요", "같아요", "같은", "너무", "자꾸", "계속", "갑자기", "요즘", "오늘", "어제", "정말",
}


def _korean_meaningful_tokens(query: str, max_tokens: int = 6) -> list:
    """질의에서 조사·어미·불용어를 제거한 의미 토큰 추출 (tsvector/ILIKE 매칭률 개선)."""
    clean = _re_kw.sub(r"[^\w\s가-힣a-zA-Z0-9]", " ", query or "")
    out = []
    for tok in clean.split():
        t = _KW_PARTICLE_RE.sub("", tok)
        if len(t) >= 2 and t not in _KW_STOP and t not in out:
            out.append(t)
        if len(out) >= max_tokens:
            break
    return out


def _sparse_search(
    query: str,
    source_types: Optional[List[str]],
    limit: int = _SPARSE_LIMIT,
) -> List[dict]:
    """
    tsvector ts_rank 기반 sparse BM25 검색.

    한국어 처리 전략:
    - content_tsv가 'simple' config로 생성된 경우 plainto_tsquery('simple', ...)가 맞음.
    - 그러나 한글은 형태소 분리 없이 공백 단위로만 토큰화되므로,
      tsvector에 없는 부분어(예: '발열' vs '발열이')가 매칭 실패하는 경우가 있음.
    - 1차 시도: plainto_tsquery('simple', query) — tsvector @@ tsquery
    - 1차 결과 0건이면 2차 fallback: content ILIKE 패턴 매칭 (공백 분리 키워드 AND)
      → sparse hits = 0 문제 우회, RRF에서 dense 결과와 융합됨

    Returns:
        dense_search와 동일한 필드 구조 + "ts_score"
    """
    from dbcommon import get_conn, _ph

    # 쿼리 전처리: 특수문자 제거, 공백 정규화 (한글 토크나이저 실패 방지)
    import re as _re
    clean_query = _re.sub(r"[^\w\s가-힣a-zA-Z0-9]", " ", query).strip()
    if not clean_query:
        clean_query = query

    # 의미 토큰(조사·어미 제거) — tsvector OR 질의 + ILIKE fallback 공용
    _kw_tokens = _korean_meaningful_tokens(query)
    # 동의어 확장 (일반인 표현↔의학 용어 — recall 보강, 실패 시 원본 유지)
    try:
        from synonym_expander import expand_tokens as _expand_syn
        _kw_tokens = _expand_syn(_kw_tokens)
    except Exception:
        pass
    # tsvector OR 질의식: '가슴 | 통증 | 답답' (to_tsquery용, 한글/영숫자만)
    _safe_tokens = [_re.sub(r"[^가-힣a-zA-Z0-9]", "", t) for t in _kw_tokens]
    _safe_tokens = [t for t in _safe_tokens if t]
    _tsquery_or = " | ".join(_safe_tokens)

    def _tsq_sql_param():
        """OR 토큰이 있으면 to_tsquery(OR), 없으면 plainto_tsquery(전체질의)."""
        if _tsquery_or:
            return "to_tsquery('simple', %s)", _tsquery_or
        return "plainto_tsquery('simple', %s)", clean_query

    def _run_tsv_search(conn, cur, q_str, src_types, lim):
        """1차: tsvector 검색 (의미토큰 OR 우선, 없으면 plainto AND)."""
        _tsq, _tsqp = _tsq_sql_param()
        if src_types:
            ph_list = _ph(len(src_types))
            sql = f"""
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.content,
                    c.section_path,
                    c.symptom_tags,
                    c.severity,
                    c.evidence_country,
                    c.evidence_topic,
                    c.regulatory_korea,
                    c.topic_keywords,
                    d.source_id,
                    d.evidence_level,
                    d.title,
                    ts_rank(c.content_tsv, {_tsq}) AS ts_score
                FROM kb_chunks c
                JOIN kb_documents d ON c.document_id = d.id
                WHERE d.status = 'active'
                  AND d.source_id = ANY(ARRAY[{ph_list}]::text[])
                  AND c.content_tsv @@ {_tsq}
                ORDER BY ts_score DESC
                LIMIT %s
            """
            params = [_tsqp] + src_types + [_tsqp, lim]
        else:
            sql = f"""
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.content,
                    c.section_path,
                    c.symptom_tags,
                    c.severity,
                    c.evidence_country,
                    c.evidence_topic,
                    c.regulatory_korea,
                    c.topic_keywords,
                    d.source_id,
                    d.evidence_level,
                    d.title,
                    ts_rank(c.content_tsv, {_tsq}) AS ts_score
                FROM kb_chunks c
                JOIN kb_documents d ON c.document_id = d.id
                WHERE d.status = 'active'
                  AND c.content_tsv @@ {_tsq}
                ORDER BY ts_score DESC
                LIMIT %s
            """
            params = [_tsqp, _tsqp, lim]
        cur.execute(sql, params)
        return cur.fetchall()

    def _run_ilike_fallback(conn, cur, tokens, src_types, lim):
        """2차 fallback: 의미토큰 OR ILIKE 매칭 + 매칭수 랭킹 (tsvector 0건 시 사용)."""
        if not tokens:
            return []
        # 의미토큰 OR ILIKE + 매칭 토큰 수로 랭킹 (AND는 과다제약으로 0건 → OR로 recall 확보)
        or_conditions = " OR ".join("c.content ILIKE %s" for _ in tokens)
        score_expr = " + ".join("(CASE WHEN c.content ILIKE %s THEN 1 ELSE 0 END)" for _ in tokens)
        like_params = [f"%{t}%" for t in tokens]
        _cols = ("c.id AS chunk_id, c.document_id, c.content, c.section_path, "
                 "c.symptom_tags, c.severity, c.evidence_country, c.evidence_topic, "
                 "c.regulatory_korea, c.topic_keywords, d.source_id, d.evidence_level, d.title, d.source_url")
        if src_types:
            ph_list = _ph(len(src_types))
            sql = f"""
                SELECT {_cols},
                    ({score_expr}) * 0.01 AS ts_score
                FROM kb_chunks c
                JOIN kb_documents d ON c.document_id = d.id
                WHERE d.status = 'active'
                  AND d.source_id = ANY(ARRAY[{ph_list}]::text[])
                  AND ({or_conditions})
                ORDER BY ts_score DESC
                LIMIT %s
            """
            params = like_params + src_types + like_params + [lim]
        else:
            sql = f"""
                SELECT {_cols},
                    ({score_expr}) * 0.01 AS ts_score
                FROM kb_chunks c
                JOIN kb_documents d ON c.document_id = d.id
                WHERE d.status = 'active'
                  AND ({or_conditions})
                ORDER BY ts_score DESC
                LIMIT %s
            """
            params = like_params + like_params + [lim]
        cur.execute(sql, params)
        return cur.fetchall()

    rows = []
    used_fallback = False
    try:
        with get_conn() as (conn, cur):
            rows = _run_tsv_search(conn, cur, clean_query, source_types, limit)
            if not rows and _kw_tokens:
                # 1차 tsvector 0건 → 2차 ILIKE fallback
                logger.info(
                    "[sparse_search] tsvector 0건 → ILIKE fallback 시도 "
                    "query=%r tokens=%s", query[:50], _kw_tokens
                )
                rows = _run_ilike_fallback(conn, cur, _kw_tokens, source_types, limit)
                used_fallback = True
    except Exception as _e:
        # sparse는 선택적 — 오류 시 dense만으로 진행 (RRF에서 dense가 커버)
        logger.warning("[sparse_search] 오류로 sparse 스킵: %s", _e)
        rows = []

    if used_fallback:
        logger.info(
            "[sparse_search] ILIKE fallback 결과 %d건 query=%r", len(rows), query[:50]
        )

    results = []
    for row in rows:
        r = dict(row)
        r["ts_score"] = float(r.get("ts_score") or 0.0)
        r["boost_reasons"] = []
        results.append(r)
    return results


# ════════════════════════════════════════════════════════════
#  Step C: RRF Fusion
# ════════════════════════════════════════════════════════════
def rrf_fusion(
    dense_results: List[dict],
    sparse_results: List[dict],
    k: int = _RRF_K,
) -> List[dict]:
    """
    Reciprocal Rank Fusion.

    각 리스트에서의 순위를 역수 합산해 두 검색 결과를 통합한다.
    score = Σ ( 1 / (k + rank) )

    Args:
        dense_results:  dense 검색 결과 (순위 순으로 정렬됨)
        sparse_results: sparse 검색 결과 (순위 순으로 정렬됨)
        k: RRF 파라미터 (기본 60)

    Returns:
        RRF 점수로 재정렬된 결과 리스트 (score 필드 포함)
    """
    scores: dict = {}
    metadata: dict = {}  # chunk_id → 메타 캐시

    for rank, r in enumerate(dense_results):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in metadata:
            metadata[cid] = r

    for rank, r in enumerate(sparse_results):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in metadata:
            metadata[cid] = r

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    fused = []
    for cid, rrf_score in sorted_items:
        item = dict(metadata[cid])
        item["rrf_score"] = rrf_score   # RRF 점수 별도 보존 (진단용)
        item["score"] = rrf_score       # 하위 호환 score 필드 유지
        # cosine_score: dense 결과에서 전달됨. sparse-only 청크는 0.0 보장
        if "cosine_score" not in item:
            item["cosine_score"] = 0.0
        if "boost_reasons" not in item:
            item["boost_reasons"] = []
        fused.append(item)
    return fused


# ════════════════════════════════════════════════════════════
#  Step C.5: Source Priority 가중 reranker (스펙 §5.3)
# ════════════════════════════════════════════════════════════
_EVIDENCE_LEVEL_SCORE = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25, "F": 0.1}


def _freshness_score(date_str, today=None) -> float:
    """발행/개정일(ISO 'YYYY-MM-DD…') → 신선도 0~1. 의학정보는 최신성=정확성.

    최근 1년 이내 1.0 → 6년에 걸쳐 0.3까지 선형 감쇠. 미상/파싱불가/미래 날짜는
    0.5(중립) — 날짜 미색인 문서는 기존 동작과 동일(무회귀).
    today: 테스트 결정성용 기준일(미지정 시 date.today()).
    """
    if not date_str:
        return 0.5
    try:
        from datetime import date
        s = str(date_str)[:10]
        doc = date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
        ref = today or date.today()
        years = (ref - doc).days / 365.0
        if years < 0:
            return 0.5
        if years <= 1:
            return 1.0
        if years >= 6:
            return 0.3
        return round(1.0 - (years - 1) * (0.7 / 5.0), 3)
    except Exception:
        return 0.5


def _weighted_rerank(
    fused: List[dict],
    dense_results: List[dict],
    sparse_results: List[dict],
) -> List[dict]:
    """
    스펙 §5.3 Hybrid 가중식으로 base score 재계산:
      0.30*keyword + 0.25*vector + 0.20*source_priority + 0.10*freshness
      + 0.10*domain_match + 0.05*evidence_level
      − jurisdiction_mismatch_penalty − low_authority_penalty

    keyword = sparse 순위 정규화, vector = cosine_score.
    source_priority는 chunk.source_priority(없으면 source_priority_for),
    freshness는 revised_at 미색인이라 중립(0.5), domain은 topic_alignment_score.
    red_flag/country boost는 이 base score 위에 곱해진다(이후 단계).
    """
    try:
        from retrieval_router import source_priority_for
    except Exception:
        def source_priority_for(_sid):
            return 3
    s_rank = {r["chunk_id"]: i for i, r in enumerate(sparse_results)}
    n_s = max(len(sparse_results), 1)
    for c in fused:
        cid = c.get("chunk_id")
        vec = float(c.get("cosine_score") or 0.0)
        vec = min(max(vec, 0.0), 1.0)
        kw = (1.0 - s_rank[cid] / n_s) if cid in s_rank else 0.0
        sp = c.get("source_priority")
        if sp is None:
            sp = source_priority_for(c.get("source_id", ""))
        try:
            sp = int(sp)
        except Exception:
            sp = 3
        sp_score = max(0.0, (7 - sp) / 6.0)             # 1→1.0 … 6→0.17
        # 신선도: 개정일/발행일이 chunk에 있으면 반영, 없으면 0.5 중립(무회귀).
        # (날짜 색인은 후속 — 마이그레이션+SELECT+ingestion. 로직은 선반영.)
        fresh = _freshness_score(c.get("revised_at") or c.get("published_at"))
        dom = float(c.get("topic_alignment_score") or 0.5)
        dom = min(max(dom, 0.0), 1.0)
        evl = _EVIDENCE_LEVEL_SCORE.get((c.get("evidence_level") or "").upper(), 0.5)
        penalty = 0.0
        juris = c.get("evidence_country") or "KR"
        if juris and juris != "KR":
            penalty += 0.10                               # jurisdiction_mismatch
        if sp > 4:
            penalty += 0.10                               # low_authority
        final = (0.30 * kw + 0.25 * vec + 0.20 * sp_score
                 + 0.10 * fresh + 0.10 * dom + 0.05 * evl) - penalty
        c["weighted_base"] = round(final, 5)
        c["score"] = c["weighted_base"]
    fused.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return fused


# ════════════════════════════════════════════════════════════
#  Step D: Red Flag Boost
# ════════════════════════════════════════════════════════════
def detect_symptom_keys(query: str, checklists: dict) -> List[str]:
    """
    질의 텍스트에서 매칭되는 symptom_key를 추출한다.

    consultation_checklists.json의 required_questions.keywords를
    질의 문자열에서 찾아 해당 증상 키를 반환한다.

    Args:
        query: 사용자 질의 텍스트
        checklists: _load_checklists() 반환값 {"symptoms": {...}}

    Returns:
        매칭된 symptom_key 리스트 (중복 제거)
    """
    matched = []
    # 1차: 증상 이름·세부표현·동의어 기반 매칭 (symptom_matcher — 구어체 도달률 개선).
    #      "머리아파"→headache 같이 증상 표현 자체로 도달. 실패해도 무해(아래 키워드 매칭 보강).
    try:
        from symptom_matcher import match_symptoms
        matched.extend(match_symptoms(query))
    except Exception:
        pass
    # 2차: 기존 문진/red_flag 키워드 매칭 (호환 — 누락분 보강)
    symptoms = checklists.get("symptoms", {})
    for symptom_key, data in symptoms.items():
        found = False
        for q in data.get("required_questions", []):
            if found:
                break
            for kw in q.get("keywords", []):
                if kw in query:
                    matched.append(symptom_key)
                    found = True
                    break
        # red_flags 키워드로도 매칭
        if not found:
            for rf in data.get("red_flags", []):
                for kw in rf.get("keywords", []):
                    if kw in query:
                        matched.append(symptom_key)
                        found = True
                        break
                if found:
                    break
    return list(dict.fromkeys(matched))  # 순서 보존 dedup (matcher 우선순위 유지)


def apply_red_flag_boost(
    results: List[dict],
    query: str,
    checklists: dict,
) -> List[dict]:
    """
    red_flag boost 적용.

    - 질의에 매칭되는 증상의 red_flag 키워드가 청크 본문에 포함되면 점수 ×1.3
    - 청크 메타의 severity='emergency'이면 추가 ×1.2

    Args:
        results: RRF 점수가 담긴 청크 리스트
        query: 사용자 질의
        checklists: consultation_checklists 딕셔너리

    Returns:
        boost_reasons가 갱신된 결과 리스트
    """
    matched_symptoms = detect_symptom_keys(query, checklists)
    if not matched_symptoms:
        return results

    # 매칭된 증상들의 red_flag 키워드 수집
    red_flag_keywords: set = set()
    symptoms = checklists.get("symptoms", {})
    for sym in matched_symptoms:
        sym_data = symptoms.get(sym, {})
        for rf in sym_data.get("red_flags", []):
            for kw in rf.get("keywords", []):
                red_flag_keywords.add(kw)

    sym_label = ",".join(matched_symptoms)

    for r in results:
        content = r.get("content", "")
        if any(kw in content for kw in red_flag_keywords):
            r["score"] = r.get("score", 0.0) * 1.3
            r["boost_reasons"].append(f"red_flag:{sym_label}")

        if r.get("severity") == "emergency":
            r["score"] = r.get("score", 0.0) * 1.2
            r["boost_reasons"].append("severity_emergency")

    return results


# ════════════════════════════════════════════════════════════
#  Step E: evidence_topic 검증 (양현종 자문 반영)
# ════════════════════════════════════════════════════════════
def check_evidence_topic_alignment(
    results: List[dict],
    query: str,
    embedding_provider=None,
    threshold: float = 0.20,
) -> List[dict]:
    """
    각 청크의 evidence_topic이 질의와 의미적으로 연결되는지 검증.
    완전히 무관한 청크(예: 소아 발열 질의에 항말라리아제 자료)에 낮은
    topic_alignment_score를 부여한다. **청크를 제거하지는 않으며**, 실제
    컷오프(게이팅)는 evaluate_retrieval_gate()가 score를 보고 판단한다.

    양현종(소아청소년과) 자문 반영:
    - "소아 발열 시나리오에서 아토피·movement disorder·항말라리아제 참고문헌이
       노출된 문제"를 score 기반 게이트로 걸러낸다.

    Args:
        results: boost 적용 후 청크 리스트
        query: 사용자 질의
        embedding_provider: 임베딩 프로바이더 인스턴스
        threshold: 코사인 유사도 임계값 (기본 0.20, 한글 임베딩 의미공간 기준)

    Returns:
        입력 청크 전체(제거 없음). evidence_topic이 있는 청크에는
        topic_alignment_score 필드가 추가됨(낮아도 유지). evidence_topic이
        없는 청크는 score 미부여로 그대로 통과.
    """
    if not results:
        return results

    # evidence_topic이 있는 청크만 검증 대상
    topics = [r.get("evidence_topic") or "" for r in results]
    if not any(topics):
        return results  # 모두 비어있으면 검증 스킵

    if embedding_provider is None:
        embedding_provider = _get_embedding_provider()

    try:
        import numpy as np
        topic_vecs = embedding_provider.embed(
            [t if t else "unknown" for t in topics]
        )
        query_vec = embedding_provider.embed([query])[0]

        qv = np.array(query_vec, dtype=float)
        qv_norm_val = float(np.linalg.norm(qv))
        if qv_norm_val == 0:
            return results
        qv_normalized = qv / qv_norm_val

        # 청크를 절대 제거하지 않음 — topic_alignment_score 필드만 부여.
        # threshold 미달이어도 청크를 유지해야 gate의 chunk_count / top1_cosine이
        # 올바르게 계산된다. 임계값 판단은 evaluate_retrieval_gate()가 담당.
        for r, tv in zip(results, topic_vecs):
            if not r.get("evidence_topic"):
                # evidence_topic 없는 청크: score 미부여 (gate에서 자동 통과 처리)
                continue
            tv_arr = np.array(tv, dtype=float)
            tv_norm_val = float(np.linalg.norm(tv_arr))
            if tv_norm_val == 0:
                continue
            tv_normalized = tv_arr / tv_norm_val
            sim = float(qv_normalized @ tv_normalized)
            r["topic_alignment_score"] = sim
            if sim < threshold:
                logger.debug(
                    "[RAGEngine] topic 낮음 (유지) chunk_id=%s topic=%s sim=%.2f < %.2f",
                    r.get("chunk_id"),
                    r.get("evidence_topic"),
                    sim,
                    threshold,
                )
        # 전체 반환 (제거 없음)
        return results

    except Exception as e:
        logger.warning(
            "[RAGEngine] evidence_topic 검증 실패 (스킵): %s", e
        )
        return results


# ════════════════════════════════════════════════════════════
#  Step F: evidence_country='KR' 부스팅
# ════════════════════════════════════════════════════════════
def apply_country_boost(results: List[dict]) -> List[dict]:
    """
    한국 의료 환경 자료 우선 부스팅.

    - evidence_country='KR' → ×1.15
    - regulatory_korea=True  → ×1.1  (심평원·식약처 기준 관련)

    양현종 자문: 해외 가이드라인을 국내에 그대로 적용하면 안 되는 분야 존재.
    KR 표기 자료를 우선 노출해 한국 의료 환경 반영.
    """
    from dbcommon import _pg_json_loads_or

    for r in results:
        if r.get("evidence_country") == "KR":
            r["score"] = r.get("score", 0.0) * 1.15
            r["boost_reasons"].append("country_kr")

        reg_val = r.get("regulatory_korea")
        # PostgreSQL BOOLEAN 또는 SQLite INTEGER / 문자열 모두 대응
        if reg_val is True or reg_val == 1 or reg_val == "true" or reg_val == "1":
            r["score"] = r.get("score", 0.0) * 1.1
            r["boost_reasons"].append("regulatory_korea")

    return results


# ════════════════════════════════════════════════════════════
#  메인 진입점: hybrid_search
# ════════════════════════════════════════════════════════════
def hybrid_search(
    query: str,
    top_k: int = 5,
    source_types: Optional[List[str]] = None,
    enable_red_flag_boost: bool = True,
    enable_evidence_topic_check: bool = True,
) -> List[dict]:
    """
    Hybrid RAG retrieval (pgvector cosine + tsvector BM25, RRF fusion)
    + 자문 반영 보정:
      - red_flag boost (consultation_checklists)
      - evidence_topic 검증 (양현종 자문: 무관한 청크 차단)
      - evidence_country='KR' 부스팅

    SQLite 모드에서는 NotImplementedError 발생.

    Args:
        query: 사용자 질의 텍스트
        top_k: 반환할 최대 청크 수 (기본 5)
        source_types: source_id 필터 리스트 (None이면 전체)
        enable_red_flag_boost: red_flag boost 활성화 (기본 True)
        enable_evidence_topic_check: evidence_topic 정렬 검증 활성화 (기본 True)

    Returns:
        [
          {
            "chunk_id": str,
            "document_id": str,
            "content": str,
            "section_path": list,
            "score": float,
            "source_id": str,
            "evidence_level": str,
            "evidence_topic": str,
            "boost_reasons": list[str],
            "topic_alignment_score": float (optional),
            ...
          }, ...
        ]

    Raises:
        NotImplementedError: SQLite 모드에서 호출 시
        ValueError: query가 비어있을 때
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    # SQLite 모드 차단
    _require_postgres()

    logger.info("[RAGEngine] hybrid_search 시작 query=%r top_k=%d", query[:50], top_k)

    # Step A: Dense 임베딩 + 검색
    embedding_provider = _get_embedding_provider()
    query_embedding = embedding_provider.embed([query])[0]
    dense_results = _dense_search(query_embedding, source_types, limit=_DENSE_LIMIT)

    logger.debug("[RAGEngine] dense 결과 %d개", len(dense_results))

    # Step B: Sparse 검색
    sparse_results = _sparse_search(query, source_types, limit=_SPARSE_LIMIT)

    logger.debug("[RAGEngine] sparse 결과 %d개", len(sparse_results))

    # Step C: RRF 융합
    fused = rrf_fusion(dense_results, sparse_results, k=_RRF_K)
    _cnt_after_rrf = len(fused)

    # Step C.5: Source Priority 가중 reranker (스펙 §5.3, 플래그 — boost 전 base score)
    if os.environ.get("RAG_HYBRID_WEIGHTED", "0") == "1":
        fused = _weighted_rerank(fused, dense_results, sparse_results)

    # Step D: red_flag boost
    if enable_red_flag_boost:
        fused = apply_red_flag_boost(fused, query, CHECKLISTS)
    _cnt_after_red_flag = len(fused)

    # Step E: evidence_topic 검증
    # threshold 0.4는 한글 임베딩 의미공간에서 너무 엄격 (전 청크 탈락 사례 확인).
    # 0.2로 완화 — 명백히 무관한 청크만 차단 (양현종 자문 의도는 유지).
    # ENABLE_EVIDENCE_TOPIC_CHECK=false 환경변수로 일시 우회 가능
    _effective_topic_check = enable_evidence_topic_check and ENABLE_EVIDENCE_TOPIC_CHECK
    if _effective_topic_check:
        fused = check_evidence_topic_alignment(
            fused, query, embedding_provider, threshold=0.2
        )
    elif not ENABLE_EVIDENCE_TOPIC_CHECK:
        logger.warning(
            "[hybrid_search] evidence_topic 검증 비활성화 (ENABLE_EVIDENCE_TOPIC_CHECK=false) "
            "query=%r", query[:50],
        )
    _cnt_after_topic = len(fused)

    # 단계별 필터링 건수 로깅 (0건 원인 진단용)
    logger.info(
        "[hybrid_search] query=%r dense=%d sparse=%d after_rrf=%d "
        "after_red_flag=%d after_topic=%d",
        query[:50],
        len(dense_results),
        len(sparse_results),
        _cnt_after_rrf,
        _cnt_after_red_flag,
        _cnt_after_topic,
    )
    if _cnt_after_topic == 0 and _cnt_after_rrf > 0:
        logger.warning(
            "[hybrid_search] 전체 청크가 topic_alignment 필터에서 제거됨 "
            "query=%r threshold=0.2 rrf_count=%d",
            query[:50], _cnt_after_rrf,
        )

    # Step F: evidence_country='KR' 부스팅
    fused = apply_country_boost(fused)

    # 최종 정렬 후 top_k 반환
    fused.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    results = fused[:top_k]

    # section_path JSON 파싱 (TEXT로 저장된 경우)
    for r in results:
        sp = r.get("section_path")
        if isinstance(sp, str):
            try:
                r["section_path"] = json.loads(sp)
            except Exception:
                r["section_path"] = [sp]
        elif sp is None:
            r["section_path"] = []

    logger.info(
        "[RAGEngine] hybrid_search 완료: %d개 반환 (top score=%.4f)",
        len(results),
        results[0].get("score", 0.0) if results else 0.0,
    )
    return results


# ════════════════════════════════════════════════════════════
#  Phase A: evaluate_retrieval_gate — Stage 1 Retrieval Gate
# ════════════════════════════════════════════════════════════

def evaluate_retrieval_gate(chunks: List[Dict]) -> Dict:
    """
    Stage 1 Retrieval Gate (설계 문서 §3 — Phase A 핵심).

    hybrid_search()가 반환한 청크 목록을 평가해 LLM 호출 가부를 결정한다.

    판정 기준:
      PASS         : top1 cosine >= 0.55 이고 (관련 청크 >= 3 + topic_match >= 2)
                     또는 (top1 >= 0.55 이고 weighted_score >= 2.0)
      WEAK_PASS    : top1 cosine >= 0.42 이고 관련 청크 >= 1 이고 topic_match >= 1
      INSUFFICIENT : 위 모든 조건 미충족 또는 청크 0건

    Args:
        chunks: hybrid_search()가 반환한 청크 리스트.
                각 청크에 cosine_score, evidence_level, topic_alignment_score 포함.

    Returns:
        {
            "decision":        "PASS" | "WEAK_PASS" | "INSUFFICIENT",
            "evidence_quality": "high" | "medium" | "low" | "insufficient",
            "top1_score":      float,
            "chunk_count":     int,
            "weighted_score":  float,
            "topic_match_count": int,
            "relevant_count":  int,
            "evidence_levels": dict,  # {"A": N, "B": N, "C": N}
            "blocked_reasons": list,  # INSUFFICIENT 사유
        }
    """
    if not chunks:
        return {
            "decision": "INSUFFICIENT",
            "evidence_quality": "insufficient",
            "top1_score": 0.0,
            "chunk_count": 0,
            "weighted_score": 0.0,
            "topic_match_count": 0,
            "relevant_count": 0,
            "evidence_levels": {},
            "blocked_reasons": ["no_chunks"],
        }

    top1 = chunks[0]
    # cosine_score 우선 참조 (dense search 원점수). sparse-only 청크는 0.0.
    # score(RRF) 필드는 gate 판정에 사용하지 않음 — 단위 불일치(0.02~0.03 vs 0.55 기준)
    top1_cosine = float(top1.get("cosine_score") or 0.0)

    # 관련 청크: cosine_score >= GATE_RELEVANT_COSINE
    relevant = [c for c in chunks if float(c.get("cosine_score") or 0.0) >= GATE_RELEVANT_COSINE]

    # topic_match: topic_alignment_score 필드가 있는 청크만 임계값 비교.
    # 필드가 없는 청크(evidence_topic 미라벨링)는 자동 통과 처리 — false negative 방지.
    topic_match = 0
    for c in chunks:
        if "topic_alignment_score" in c:
            # 필드 존재: 임계값 비교 (라벨링된 청크는 엄격히 검증)
            if float(c["topic_alignment_score"]) >= GATE_TOPIC_ALIGNMENT_THRESHOLD:
                topic_match += 1
        else:
            # 필드 없음: 통과 (evidence_topic 미라벨링 청크는 일단 신뢰)
            topic_match += 1

    # evidence_level 가중 합산 (cosine 미달 청크는 0.5 패널티)
    weighted = sum(
        EVIDENCE_LEVEL_WEIGHT.get(c.get("evidence_level") or "C", 0.4)
        * (1.0 if float(c.get("cosine_score") or 0.0) >= GATE_RELEVANT_COSINE else 0.5)
        for c in chunks
    )

    # evidence_level 분포
    level_counts: Dict[str, int] = {}
    for c in chunks:
        lv = c.get("evidence_level") or "C"
        level_counts[lv] = level_counts.get(lv, 0) + 1

    # 분기 로직 (설계 문서 §3.3)
    blocked_reasons: List[str] = []

    if top1_cosine >= GATE_TOP1_PASS and len(relevant) >= GATE_CHUNK_COUNT_PASS and topic_match >= GATE_TOPIC_MATCH_PASS:
        decision = "PASS"
    elif top1_cosine >= GATE_TOP1_PASS and weighted >= GATE_WEIGHTED_PASS:
        decision = "PASS"
    elif top1_cosine >= GATE_TOP1_WEAK and len(relevant) >= 1 and topic_match >= 1:
        decision = "WEAK_PASS"
    else:
        decision = "INSUFFICIENT"
        if top1_cosine < GATE_TOP1_WEAK:
            blocked_reasons.append(f"top1_cosine_too_low ({top1_cosine:.3f} < {GATE_TOP1_WEAK})")
        if len(relevant) < 1:
            blocked_reasons.append("no_relevant_chunks")
        if topic_match < 1:
            blocked_reasons.append("no_topic_match")
        if not blocked_reasons:
            blocked_reasons.append("below_all_thresholds")

    # evidence_quality 매핑 (설계 문서 §7.1)
    if decision == "INSUFFICIENT":
        evidence_quality = "insufficient"
    elif decision == "WEAK_PASS":
        evidence_quality = "low"
    else:
        # PASS: A/B 청크 비율로 high/medium 구분
        ab_count = level_counts.get("A", 0) + level_counts.get("B", 0)
        citation_count = len([c for c in chunks if float(c.get("cosine_score") or 0.0) >= GATE_RELEVANT_COSINE])
        if ab_count >= 2 and citation_count >= 3:
            evidence_quality = "high"
        else:
            evidence_quality = "medium"

    return {
        "decision": decision,
        "evidence_quality": evidence_quality,
        "top1_score": top1_cosine,
        "chunk_count": len(chunks),
        "weighted_score": round(weighted, 4),
        "topic_match_count": topic_match,
        "relevant_count": len(relevant),
        "evidence_levels": level_counts,
        "blocked_reasons": blocked_reasons,
    }


# ════════════════════════════════════════════════════════════
#  T5: generate_response — 통합 RAG 응답 생성
# ════════════════════════════════════════════════════════════

# 응답 섹션 구조 검증용 — 고정 4단이 아니라 '상황별 동적 헤더 + 이모지'를 쓴다.
# 헤더 라인 패턴: 줄 시작이 이모지 / 마크다운 헤딩(##) / 굵은 제목(**) / 【…】 중 하나.
import re as _re_struct
_SECTION_HEADER_RE = _re_struct.compile(
    r"(?m)^\s*(?:"
    r"#{1,4}\s+\S"                                   # ## 제목
    r"|\*\*\S"                                        # **굵은 제목**
    r"|【.+?】"                                       # 【…】 (구형 호환)
    r"|[\U0001F300-\U0001FAFF☀-➿⬀-⯿←-⇿]"  # 이모지/기호 시작
    r")"
)

# EMERGENCY 감지 키워드
_EMERGENCY_KEYWORDS = ["119", "응급실", "긴급", "즉시 병원", "즉시 응급"]

# 인용 번호 정규식
_CITATION_PATTERN = re.compile(r'\[(\d+)\]')


# ── 트리아지(triage): 비의료·대화성 입력 감지 ───────────────────────────────
# "배고파", "안녕" 같은 비의료/대화성 입력에 4단 의료답변(응급징후 나열·문진)을
# 들이대는 과의료화를 방지한다. 보수적 설계: 증상·약물·응급·진단·crisis 등 의료
# 신호가 조금이라도 있으면 절대 발동하지 않는다(진짜 상담 무영향 → both_A 무회귀).

# 의료/건강 신호 — 하나라도 있으면 트리아지하지 않음(분류기 규칙이 놓치는 표현 보강)
_MEDICAL_SIGNAL_RE = re.compile(
    r"아프|아파|아픈|통증|쑤시|결리|저리|저림|붓|부었|부어|메스|울렁|구역|토하|"
    r"발열|오한|몸살|기침|가래|콧물|두통|복통|설사|변비|발진|가렵|두드러기|"
    r"숨|호흡|가슴|심장|혈압|혈당|당뇨|소변|대변|혈변|혈뇨|출혈|피가|상처|외상|"
    r"잠|불면|수면|피로|무기력|체중|살\s*빠|식욕|어깨|허리|관절|무릎|"
    r"피부|복용|진료|병원|검사|증상|질환|감염|코로나|독감|임신|생리|월경|열이|열은"
)

# 명백한 비의료/대화성 입력 패턴 (짧고 의료 신호 없는 입력에만 적용)
_NONMEDICAL_RE = re.compile(
    r"(안녕|하이|헬로|hello|hi\b|ㅎㅇ|반가|잘\s*지내|누구야|누구세요|이름이?\s*(뭐|무엇)|"
    r"뭐\s*해|뭐하|심심|지루|테스트|test|ㅋㅋ|ㅎㅎ|ㅇㅇ|배고|배\s*고프|허기|졸려|졸리|"
    r"목말|목\s*마르|날씨|고마워|고맙|감사|잘\s*가|바이|bye|사랑|좋아해|화이팅|파이팅|밥\s*먹)",
    re.IGNORECASE,
)


def _should_clarify(query: str, classification: Optional[Dict]) -> Optional[str]:
    """비의료/모호 입력이면 사유 문자열, 아니면 None.

    보수적 발동 조건(모두 충족 시에만): (1) 분류기 intent가 catch-all
    general_health 이고 저위험, (2) 의료/건강 신호가 전혀 없음, (3) 길이가 짧음
    (상세 서술 아님), (4) 명백한 비의료/대화성 패턴 매칭. 증상·응급·약물·진단·
    crisis 등은 분류기가 다른 intent로 잡으므로 절대 트리아지되지 않는다.
    """
    q = (query or "").strip()
    if not q:
        return "empty"
    cl = classification or {}
    if cl.get("intent", "general_health") != "general_health":
        return None
    if cl.get("risk_level", "low") != "low":
        return None
    if _MEDICAL_SIGNAL_RE.search(q):
        return None
    if len(q) > 25:
        return None
    if _NONMEDICAL_RE.search(q):
        return "non_medical_or_vague"
    return None


def _build_clarify_response() -> str:
    """비의료/모호 입력에 대한 짧은 되묻기 응답(4단 의료답변 대신)."""
    return (
        "무엇을 도와드릴까요? 건강과 관련해 불편한 증상이나 궁금한 점을 "
        "구체적으로 알려주시면(예: 언제부터 / 어디가 / 어떻게 불편한지) "
        "관련 정보를 안내해 드리겠습니다.\n\n"
        "갑작스러운 흉통·호흡곤란·의식 저하·편측 마비·심한 출혈 등 응급 증상이 "
        "있다면 즉시 119 또는 응급실을 이용하세요."
    )


def generate_response(
    query: str,
    conversation_id: str,
    provider_id: str = None,
    top_k: int = 5,
    enable_guardrails: bool = True,
    personal_findings=None,
    personal_consent: bool = False,
) -> Iterator[Dict]:
    """
    Hybrid search → 프롬프트 빌드 → LLM 스트리밍 → 가드레일 → DB 기록.

    Args:
        query: 사용자 질의 텍스트
        conversation_id: 대화 ID (conversations 테이블)
        provider_id: llm_providers.id (None이면 환경변수 기본값)
        top_k: 검색 청크 수 (기본 5)
        enable_guardrails: 가드레일 활성화 (기본 True)

    Yields:
        {"type": "INFO", "data": {"search_results": [...]}}
        {"type": "GENERATION", "text": "..."}
        {"type": "STOP", "text": "...", "rag_query_id": "...", "citations": [...],
         "latency_ms": N, "tokens": {...}, "guardrail_action": "..."}
        {"type": "ERROR", "message": "..."}
    """
    from llm_router import get_llm_provider

    start_ts = time.time()
    # 비식별 이벤트(analytics_events) 적재용 상태 — STOP 지점마다 1건 emit.
    _had_personal_block = False
    emergency_detected = False

    # 클라이언트에 즉시 상태 알림 (cold start + GPT-5 reasoning 지연 동안 멈춤 방지)
    yield {"type": "INFO", "data": {"status": "started", "query": query[:50]}}

    # ── 1. EMERGENCY_REDIRECTED 상태 체크 ─────────────────────
    conv_state = _get_conversation_state(conversation_id)
    if conv_state.get("emergency_state") == "EMERGENCY_REDIRECTED":
        emergency_msg = _build_emergency_response()
        yield {"type": "GENERATION", "text": emergency_msg}
        yield {
            "type": "STOP",
            "text": emergency_msg,
            "rag_query_id": None,
            "citations": [],
            "latency_ms": int((time.time() - start_ts) * 1000),
            "tokens": {"input": 0, "output": 0},
            "guardrail_action": "emergency_redirect",
        }
        _emit_analytics(
            "emergency_redirect", conversation_id, None,
            guardrail_action="emergency_redirect",
            latency_ms=int((time.time() - start_ts) * 1000),
            emergency=True,
        )
        return

    # ── 1.5 PII/PHI 마스킹 + 질문 분류 (스펙 통합, 가드 — 실패해도 본 흐름 유지) ──
    _classification = None
    try:
        from pii_masker import mask_pii
        _m = mask_pii(query)
        if _m.get("detected_items"):
            query = _m["masked_text"]  # PII 마스킹 질의로 전환 (HealthBench엔 PII 없어 무영향)
    except Exception as _e:
        logger.debug("[RAGEngine] PII 마스킹 스킵: %s", _e)
    try:
        from medical_classifier import classify_rule_based
        _classification = classify_rule_based(query)  # 규칙기반(무비용·무지연)
    except Exception as _e:
        logger.debug("[RAGEngine] 분류 스킵: %s", _e)

    # ── 1.6 멀티턴: 후속질의면 직전 주제로 *검색 질의* 재작성 (06 §3) ──
    # 안전 분류는 위에서 원본 질의로 끝남(§6-1). 재작성은 검색에만 적용.
    # 실패는 비차단(원본 질의 유지). intent emergency/crisis면 재작성 안 함.
    _retrieval_query = query
    _is_followup = False
    _mt_ctx = {}
    _mt_cur_keys = []
    _rewrite_method = "none"
    try:
        import conversation_context as _cc
        _mt = _cc.resolve_retrieval_query(
            query, conversation_id,
            intent=(_classification or {}).get("intent"),
        )
        _retrieval_query = _mt["retrieval_query"]
        _is_followup = _mt["is_followup"]
        _mt_ctx = _mt["context"]
        _mt_cur_keys = _mt["current_symptom_keys"]
        _rewrite_method = _mt["rewrite_method"]
        if _rewrite_method != "none":
            logger.info(
                "[RAGEngine][Multiturn] 후속질의 재작성 method=%s → 검색질의 전환",
                _rewrite_method,
            )
    except Exception as _e:
        logger.debug("[RAGEngine] 멀티턴 해석 스킵: %s", _e)

    # 진입 이벤트(비식별) — 분류 직후 1건. 퍼널 분모/intent 분포(응급 재진입 제외).
    _emit_analytics(
        "query_received", conversation_id, _classification,
        is_followup=_is_followup,
    )

    # ── 1.7 트리아지: 비의료/대화성 입력은 4단 의료답변 대신 되묻기 ──
    # "배고파", "안녕" 등 의료 신호 없는 모호 입력에 응급징후·문진을 들이대는
    # 과의료화 방지. 검색·LLM 호출을 건너뛰어 비용도 절약(0원).
    # 멀티턴 재작성이 성공하면(검색질의 확보) 되묻기를 건너뛴다 —
    # "언제 병원 가야해요?" 같은 후속질의가 비의료 모호입력으로 오인돼
    # 되묻기 막다른길에 빠지던 문제 해소.
    _clarify_reason = _should_clarify(query, _classification)
    if _clarify_reason and _rewrite_method == "none":
        logger.info(
            "[RAGEngine][Triage] 비의료/모호 입력 되묻기 query=%r reason=%s",
            query[:40], _clarify_reason,
        )
        clarify_text = _build_clarify_response()
        yield {"type": "GENERATION", "text": clarify_text}
        yield {
            "type": "STOP",
            "text": clarify_text,
            "rag_query_id": None,
            "citations": [],
            "latency_ms": int((time.time() - start_ts) * 1000),
            "tokens": {"input": 0, "output": 0},
            "guardrail_action": "triage_clarify",
        }
        _emit_analytics(
            "triage_clarify", conversation_id, _classification,
            guardrail_action="triage_clarify",
            latency_ms=int((time.time() - start_ts) * 1000),
            is_followup=_is_followup,
        )
        return

    # ── 2. Hybrid search ──────────────────────────────────────
    retrieval_start = time.time()
    try:
        chunks = hybrid_search(_retrieval_query, top_k=top_k)
    except Exception as e:
        logger.error("[RAGEngine] hybrid_search 오류: %s", e)
        yield {"type": "ERROR", "message": f"검색 오류: {e}"}
        return
    retrieval_ms = int((time.time() - retrieval_start) * 1000)

    yield {
        "type": "INFO",
        "data": {"search_results": [_format_search_result(c) for c in chunks]},
    }

    # ── 2-B. Retrieval Gate 평가 (Phase A) ────────────────────
    gate_result = evaluate_retrieval_gate(chunks)

    # EVIDENCE_CHECK SSE 이벤트 — LLM 호출 전에 클라이언트에 즉시 전달
    yield {
        "type": "EVIDENCE_CHECK",
        "data": {
            "quality": gate_result["evidence_quality"],
            "decision": gate_result["decision"],
            "top1_score": gate_result["top1_score"],
            "chunk_count": gate_result["chunk_count"],
            "relevant_count": gate_result["relevant_count"],
            "topic_match": gate_result["topic_match_count"],
            "evidence_levels": gate_result["evidence_levels"],
            "reasons": gate_result["blocked_reasons"],
        },
    }

    # INSUFFICIENT 처리 분기
    if gate_result["decision"] == "INSUFFICIENT":
        if RETRIEVAL_GATE_ENFORCE:
            # enforce 모드: LLM 호출 스킵, 템플릿 응답 반환
            logger.warning(
                "[RAGEngine][Gate] INSUFFICIENT — LLM 스킵 query=%r top1=%.3f",
                query[:50], gate_result["top1_score"],
            )
            insufficient_text = _build_insufficient_evidence_response()
            yield {"type": "GENERATION", "text": insufficient_text}

            # DB 기록
            _insert_rag_query(
                conversation_id=conversation_id,
                query_text=query,
                retrieved_chunk_ids=[c["chunk_id"] for c in chunks],
                llm_provider_id=None,
                response_text=insufficient_text,
                citations_json=[],
                latency_total_ms=int((time.time() - start_ts) * 1000),
                latency_retrieval_ms=retrieval_ms,
                latency_llm_ms=0,
                tokens={"input": 0, "output": 0},
                guardrail_violations=[],
                guardrail_action="insufficient_evidence",
                gate_result=gate_result,
            )

            yield {
                "type": "STOP",
                "text": insufficient_text,
                "rag_query_id": None,
                "citations": [],
                "latency_ms": int((time.time() - start_ts) * 1000),
                "tokens": {"input": 0, "output": 0},
                "guardrail_action": "insufficient_evidence",
                "evidence_quality": "insufficient",
                "gate_decision": "INSUFFICIENT",
            }
            _emit_analytics(
                "insufficient_evidence", conversation_id, _classification,
                guardrail_action="insufficient_evidence", gate_result=gate_result,
                citations_count=0, latency_ms=int((time.time() - start_ts) * 1000),
                is_followup=_is_followup, refusal=True,
            )
            return
        else:
            # shadow 모드: 로그만 남기고 정상 진행
            logger.warning(
                "[RAGEngine][Gate][SHADOW] INSUFFICIENT (shadow 모드 — 정상 진행) "
                "query=%r top1=%.3f reasons=%s",
                query[:50], gate_result["top1_score"], gate_result["blocked_reasons"],
            )

    elif gate_result["decision"] == "WEAK_PASS":
        logger.info(
            "[RAGEngine][Gate] WEAK_PASS query=%r top1=%.3f weighted=%.3f",
            query[:50], gate_result["top1_score"], gate_result["weighted_score"],
        )

    else:
        logger.info(
            "[RAGEngine][Gate] PASS query=%r quality=%s top1=%.3f",
            query[:50], gate_result["evidence_quality"], gate_result["top1_score"],
        )

    # ── 3. 프롬프트 조립 ──────────────────────────────────────
    system_prompt = _build_rag_system_prompt(query, chunks, gate_result=gate_result)
    user_prompt = _build_rag_user_prompt(query, chunks)

    # ── 4. LLM 스트리밍 (단일 스레드 — diag로 0.7~0.9초 정상 확인됨) ──
    # 리즈닝 침묵 동안 SSE가 끊겨도(truncation) 서버는 끝까지 생성·저장하고
    # 프론트가 /api/rag/result 로 폴링 복구하므로 별도 스레드 keep-alive 불필요.
    llm_start = time.time()
    provider = get_llm_provider(provider_id)

    # 방향 2: 비식별 개인 맥락(밴드 라벨만)을 LLM 프롬프트에 주입 — 플래그·동의·국외이전·
    # 응급 게이트로 통제(정본 17). 기본 off → 미설정 시 행동 변화 0. 원시값·진단명 미투입.
    try:
        import personal_llm_context as _plc
        _pctx = _plc.build_llm_context(
            personal_findings, query,
            consent=personal_consent, provider=provider,
            is_emergency=((_classification or {}).get("intent") == "emergency"),
        )
        if _pctx:
            system_prompt = system_prompt + "\n\n" + _pctx
            logger.info("[RAGEngine] 비식별 개인맥락 LLM 주입(밴드 라벨만, 동의·게이트 통과)")
    except Exception as _e:
        logger.debug("[RAGEngine] 개인맥락 주입 스킵: %s", _e)

    full_text = ""
    tokens = {"input": 0, "output": 0}

    _last_keepalive = time.time()
    for chunk_event in provider.stream_chat(system_prompt, user_prompt):
        if chunk_event["type"] == "GENERATION":
            full_text += chunk_event["text"]
            yield chunk_event
            now = time.time()
            if now - _last_keepalive >= 20:
                yield {"type": "KEEP_ALIVE"}
                _last_keepalive = now
        elif chunk_event["type"] == "STOP":
            full_text = chunk_event["text"]
            tokens = chunk_event.get("tokens", {"input": 0, "output": 0})
        elif chunk_event["type"] == "ERROR":
            yield chunk_event
            return

    llm_ms = int((time.time() - llm_start) * 1000)
    # 진단: 1차 LLM 스트리밍이 완료됐는지(여기 도달하면 스트리밍 OK, 행은 이후 단계)
    logger.info("[RAGEngine] LLM1 스트리밍 완료 llm_ms=%d len=%d", llm_ms, len(full_text))

    # ── 5. 가드레일 후처리 ────────────────────────────────────
    guardrail_result = {"action": "pass", "violations": []}

    if enable_guardrails:
        try:
            from analyzer import ComplianceAnalyzer
            analyzer = ComplianceAnalyzer()
            analysis = analyzer.analyze(full_text, user_input=query)
            violations = analysis.violations if hasattr(analysis, "violations") else []
            # AnalysisResult 객체 → dict 리스트로 변환 (context 포함 — FP 필터용)
            violations_dicts = []
            for v in violations:
                violations_dicts.append({
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "matched_text": v.matched_text,
                    "context": getattr(v, "context", "") or "",
                })

            # RAG 전용 오탐 필터 — 교육적/면책/부정 문맥 위반 제거 (재생성·오차단 감소)
            # 공용 analyzer 무변경. 실제 지시/용량/단정진단은 보존.
            violations_dicts, _fp_dropped = _filter_guardrail_false_positives(violations_dicts)
            if _fp_dropped:
                logger.info(
                    "[RAGEngine] 가드레일 오탐 필터 제거=%s (재생성/차단 방지)",
                    [(d.get("severity"), d.get("rule_id")) for d in _fp_dropped],
                )

            # CRITICAL 차단
            critical = [v for v in violations_dicts if v.get("severity") == "CRITICAL"]
            if critical:
                full_text = (
                    "죄송합니다. 안전 기준에 부합하는 응답을 생성하지 못했습니다. "
                    "의료진과의 직접 상담을 권유합니다."
                )
                guardrail_result = {
                    "action": "blocked",
                    "violations": [v["rule_id"] for v in critical],
                }
                logger.warning(
                    "[RAGEngine] 가드레일 CRITICAL 차단 violations=%s",
                    guardrail_result["violations"],
                )

            # HIGH 재생성 1회
            elif any(v.get("severity") == "HIGH" for v in violations_dicts):
                high_violations = [v for v in violations_dicts if v.get("severity") == "HIGH"]
                _regen_start = time.time()
                full_text = _regenerate_with_warning(
                    provider, system_prompt, user_prompt, violations_dicts
                )
                _regen_ms = int((time.time() - _regen_start) * 1000)
                guardrail_result = {
                    "action": "regenerated",
                    "violations": [v["rule_id"] for v in high_violations],
                }
                logger.info(
                    "[RAGEngine] 가드레일 HIGH 재생성 violations=%s 재생성=%dms (gen=%dms, 총지연 2배 영향)",
                    guardrail_result["violations"], _regen_ms, llm_ms,
                )

            # 인용 검증
            full_text, citations_action = _validate_and_fix_citations(
                full_text, chunks, system_prompt, user_prompt
            )
            if citations_action == "regenerated":
                guardrail_result["action"] = "regenerated_citation"

            # EMERGENCY 잠금은 *사용자 질의 분류*(intent=emergency)로만 판정한다.
            # 답변 본문(4단 구조의 【① 즉시 행동】)·면책문구에는 "…면 119/응급실"
            # 같은 조건부 안내가 정상 답변에도 흔히 들어가므로, 답변 텍스트를 스캔하면
            # 일반 대화가 영구 응급-리다이렉트로 고착된다(과대 트리아지, 레드팀 #4).
            # 분류기는 구어체·부사삽입 내성을 갖춰 실제 응급 질의를 잡는다.
            emergency_detected = (_classification or {}).get("intent") == "emergency"

            # ── 개인화 주입 (P1a, 정본 14 §6 — C19 렌더 + C20 백스톱) ──
            # 결정적 로컬 findings → 안전 블록을 답변에 후append. 개인 데이터는 LLM
            # 프롬프트에 미투입(stream_chat 직전 원시값 스캔 0이 구조적으로 보장).
            # EMERGENCY/triage는 개인화 생략(I7). safe_block이 관련성 게이트+C20을
            # 내포하며 위반/무관 시 ""(fail-closed) → 답변 무변경.
            if personal_findings and not emergency_detected:
                try:
                    import personal_context as _pc
                    _pblock = _pc.safe_block(personal_findings, query)
                    if _pblock:
                        full_text = full_text.rstrip() + "\n\n" + _pblock
                        _had_personal_block = True
                except Exception as _pe:
                    logger.debug("[RAGEngine] 개인화 주입 스킵: %s", _pe)

            # 면책조항 자동 부착 (하단)
            full_text = _ensure_disclaimer(full_text)
            # 상단 고지 자동 부착 (필수 고정 문구 — 119·응급실 문구 포함)
            full_text = _ensure_top_disclaimer(full_text)

            # 섹션 헤더 가독성 검증(동적 헤더 2개 이상) — 라벨용, 차단 안 함
            structure_ok = _has_section_structure(full_text)
            if not structure_ok and guardrail_result["action"] == "pass":
                guardrail_result["action"] = "missing_structure"

            # EMERGENCY 감지 → 상태 전환 (면책문구 부착 전 판정값 사용)
            if emergency_detected:
                _set_conversation_state(conversation_id, "EMERGENCY_REDIRECTED")
                logger.info(
                    "[RAGEngine] EMERGENCY 감지 → conversation_id=%s EMERGENCY_REDIRECTED 전환",
                    conversation_id,
                )

        except Exception as e:
            # fail-open 완화: 가드레일이 예외로 미완료되면 'pass'로 오라벨하지 않고
            # 'error'로 표시해 감사·검수가 인지하게 한다. 면책문구는 예외 시에도
            # 반드시 부착(예외가 disclaimer 부착 전에 발생하면 누락되던 컴플라이언스 갭).
            # 가용성을 위해 응답 자체를 차단하지는 않는다(과도차단 방지).
            logger.error("[RAGEngine] 가드레일 오류 — fail-safe 처리(action=error): %s", e)
            if guardrail_result.get("action") == "pass":
                guardrail_result["action"] = "error"
            try:
                full_text = _ensure_disclaimer(full_text)
                full_text = _ensure_top_disclaimer(full_text)
            except Exception:
                pass

    # ── 6. 인용 매핑 추출 ────────────────────────────────────
    citations = _extract_citations(full_text, chunks)

    # ── 6.5 Evidence Pack + Citation Verifier (스펙 §6/§7.7) ──
    # Evidence Pack 생성→감사 기록(스펙 AC#3·#8). Citation Verifier는 [N] 답변에
    # shadow로 적용(메트릭·감사·검수큐 피드). 답변 텍스트는 미변경(무회귀).
    # verify_citations는 [1]을 E1로 정규화하므로 기존 [N] 인용을 그대로 검증한다.
    # 강제 제거(verified_answer)는 4단 구조·면책을 파괴하므로 미적용(후속: 문장단위 in-place).
    _evidence_pack = None
    _citation_result = None
    try:
        from evidence_pack import build_evidence_pack
        _evidence_pack = build_evidence_pack(query, _classification or {}, chunks)
    except Exception as _e:
        logger.debug("[RAGEngine] evidence_pack 스킵: %s", _e)
    try:
        from citation_verifier import verify_citations
        _n = len(chunks)
        _eids = [str(i) for i in range(1, _n + 1)] + [f"E{i}" for i in range(1, _n + 1)]
        _citation_result = verify_citations(full_text, _eids)
        if _citation_result:
            logger.info(
                "[RAGEngine][CiteVerify] coverage=%.2f unsupported=%d pass=%s",
                _citation_result.get("citation_coverage", 0.0),
                len(_citation_result.get("unsupported_claims", [])),
                _citation_result.get("overall_pass"),
            )
    except Exception as _e:
        logger.debug("[RAGEngine] citation_verify 스킵: %s", _e)

    # ── 6.6 claim↔근거 의미일치(어휘 겹침) shadow 검증 (07 §9.1) ──
    # 인용 마커 범위(verify_citations)를 넘어, 인용 문장이 실제 근거 청크와
    # 겹치는지 결정적으로 점검. shadow — 로그·검수 신호로만(차단/삭제 없음).
    try:
        from citation_verifier import check_citation_grounding
        _ev_by_marker = {}
        for _i, _c in enumerate(chunks, 1):
            _txt = _c.get("content") or _c.get("snippet") or ""
            _ev_by_marker[str(_i)] = _txt
            _ev_by_marker[f"E{_i}"] = _txt
        _grounding = check_citation_grounding(full_text, _ev_by_marker)
        if _grounding.get("checked") and _grounding.get("weak_claims"):
            logger.info(
                "[RAGEngine][Grounding] 근거일치율=%.2f weak=%d (shadow)",
                _grounding["grounded_ratio"], len(_grounding["weak_claims"]),
            )
    except Exception as _e:
        logger.debug("[RAGEngine] grounding shadow 스킵: %s", _e)

    # ── 7. rag_queries INSERT ─────────────────────────────────
    rag_query_id = _insert_rag_query(
        conversation_id=conversation_id,
        query_text=query,
        retrieved_chunk_ids=[c["chunk_id"] for c in chunks],
        llm_provider_id=provider.provider_id,
        response_text=full_text,
        citations_json=citations,
        latency_total_ms=int((time.time() - start_ts) * 1000),
        latency_retrieval_ms=retrieval_ms,
        latency_llm_ms=llm_ms,
        tokens=tokens,
        guardrail_violations=guardrail_result.get("violations", []),
        guardrail_action=guardrail_result["action"],
        gate_result=gate_result,
    )

    # ── 7.5 감사 필드 + 검수 큐 적재 (스펙 통합, 가드) ─────────
    try:
        if rag_query_id and _classification is not None:
            import rag_db as _rag_db
            from review_queue import should_review
            _answer_id = "ans_" + rag_query_id[:12]
            _model_v = getattr(provider, "model_id", None) or getattr(provider, "provider_id", "unknown")
            # 멀티턴 재작성 추적(06 §6-4): 재작성 방법 + 원 질의 해시(원문 미저장)
            _rewritten_from = None
            if _rewrite_method != "none":
                import hashlib as _hl
                _rewritten_from = _hl.sha1((query or "").encode("utf-8")).hexdigest()[:16]
            _rag_db.update_rag_query_audit(
                rag_query_id,
                answer_id=_answer_id,
                model_version=_model_v,
                prompt_version="rag-engine-v1",
                classification_json=json.dumps(_classification, ensure_ascii=False),
                evidence_pack_json=(
                    json.dumps(_evidence_pack, ensure_ascii=False) if _evidence_pack else None
                ),
                rewrite_method=_rewrite_method,
                rewritten_from=_rewritten_from,
            )
            _decision = should_review(
                classification=_classification,
                citation_result=(_citation_result or {
                    "overall_pass": guardrail_result["action"] != "blocked",
                    "citation_coverage": 1.0 if citations else 0.0,
                }),
                safety_result={
                    "safe_to_send": guardrail_result["action"] != "blocked",
                    "risk_flags": guardrail_result.get("violations", []),
                },
            )
            if _decision.get("needs_review"):
                _rag_db.add_review_item({
                    "answer_id": _answer_id, "rag_query_id": rag_query_id,
                    "question": query[:500], "answer": full_text[:2000],
                    "priority": _decision["priority"],
                    "assignee_role": _decision["assignee_role"],
                    "reasons": _decision["reasons"],
                })
    except Exception as _e:
        logger.debug("[RAGEngine] 감사/검수 스킵: %s", _e)

    # ── 7.6 멀티턴 세션 컨텍스트 갱신 (06 §3 step 5, 가드) ─────
    # 비식별 요약만 저장(증상키·intent·진료과). 후속질의(증상 0건)는 직전 주제를
    # carry-forward 해 대화 주제를 유지한다. 실패는 비차단.
    try:
        import conversation_context as _cc
        _persist_keys = _cc.keys_to_persist(_mt_cur_keys, _mt_ctx)
        _persist_depts = []
        if _persist_keys:
            try:
                from symptom_matcher import departments_for
                _persist_depts = departments_for(_persist_keys)
            except Exception:
                _persist_depts = []
        _cc.update_context(
            conversation_id,
            symptom_keys=_persist_keys,
            intent=(_classification or {}).get("intent"),
            departments=_persist_depts,
        )
    except Exception as _e:
        logger.debug("[RAGEngine] 멀티턴 컨텍스트 갱신 스킵: %s", _e)

    # ── 8. STOP 이벤트 ────────────────────────────────────────
    _total_ms = int((time.time() - start_ts) * 1000)
    # 지연/가드레일 측정용 요약 로그 (재생성 빈도·비용 추적)
    logger.info(
        "[RAGEngine] 응답완료 총=%dms gen=%dms 가드레일=%s 인용=%d",
        _total_ms, llm_ms, guardrail_result["action"], len(citations),
    )
    _emit_analytics(
        "answer_shown", conversation_id, _classification,
        rag_query_id=rag_query_id,
        guardrail_action=guardrail_result["action"], gate_result=gate_result,
        citations_count=len(citations), latency_ms=_total_ms,
        is_followup=_is_followup, had_personal_block=_had_personal_block,
        gave_referral=bool((_classification or {}).get("requires_clinician_consult")),
        refusal=False, emergency=emergency_detected,
    )
    yield {
        "type": "STOP",
        "text": full_text,
        "rag_query_id": rag_query_id,
        "citations": citations,
        "latency_ms": _total_ms,
        "tokens": tokens,
        "guardrail_action": guardrail_result["action"],
        "evidence_quality": gate_result["evidence_quality"],
        "gate_decision": gate_result["decision"],
    }


# ════════════════════════════════════════════════════════════
#  프롬프트 빌더
# ════════════════════════════════════════════════════════════

def _build_rag_system_prompt(query: str, chunks: List[dict], gate_result: Dict = None) -> str:
    """
    RAG 응답 생성 전용 시스템 프롬프트 (Phase A 재작성 — 설계 문서 §4.2).

    중요: 평가용 build_gpt_system_prompt()는 절대 재사용하지 않는다.
    평가 프롬프트는 JSON 점수를 반환하라고 LLM에 지시하므로,
    RAG 생성에 사용하면 LLM이 평가 JSON을 응답으로 출력한다 (실제 발견된 버그).

    Args:
        query:       사용자 질의 (미사용, 시그니처 호환 유지)
        chunks:      검색 청크 (미사용, 시그니처 호환 유지)
        gate_result: evaluate_retrieval_gate() 반환값.
                     WEAK_PASS이면 근거 제한 모드 문단을 자동 추가.
    """
    # 면책조항만 별도로 가져옴 (평가 프롬프트 X)
    _DEFAULT_TOP = (
        "본 서비스는 건강정보·교육 목적의 참고용으로 제공됩니다. "
        "질병의 진단·처방·치료·선별검사 등 의료행위를 하지 않으며, "
        "의학적 판단과 치료는 반드시 의료인에 의해 이뤄져야 합니다. "
        "응급증상 발생 시 즉시 119 또는 응급실을 이용하십시오."
    )
    try:
        from guideline_loader import get_fixed_notices
        fixed_notices = get_fixed_notices()
        top_disclaimer = fixed_notices.get("top_disclaimer", _DEFAULT_TOP) or _DEFAULT_TOP
        bottom_disclaimer = fixed_notices.get(
            "bottom_disclaimer",
            "본 정보는 참고용이며, 정확한 진단·치료는 의료진과 상담하세요.",
        )
    except Exception:
        top_disclaimer = _DEFAULT_TOP
        bottom_disclaimer = "본 정보는 참고용이며, 정확한 진단·치료는 의료진과 상담하세요."

    # 설계 문서 §4.2 신규 프롬프트 전문
    prompt = f"""당신은 한국 의료법(의료법 27조 무면허 의료행위 금지, 응급의료법)을 준수하는
건강 정보 안내 AI '나만의 주치의'입니다.

당신은 의사가 아닙니다. 진단·처방·치료를 수행하지 않습니다.
당신은 오직 아래 ## 검토 자료에 명시된 사실만 사용해 정보를 안내합니다.

## 절대 원칙 (모두 동시에 만족)
1. [근거 종속] 모든 의학적 주장의 문장 끝에 반드시 [N] 인용을 붙이시오.
   인용 없는 의학적 주장은 출력 금지.
2. [컨텍스트 외 정보 금지] 검토 자료에 없는 약물명, 용량, 검사명, 진단명을
   언급하지 마시오. 일반적 지식이라도 인용할 청크가 없으면 쓰지 마시오.
3. [근거 충돌 시 보수성] [1]과 [2]의 권고가 다르면 더 보수적인(의료진 상담을
   더 강하게 권유하는) 쪽을 선택하고 충돌 사실을 명시하시오.
4. [진단 단정 금지] OO병입니다 금지. OO 가능성을 시사합니다 [N] 로만 표현.
5. [처방·검사 지시 금지] 특정 약물 복용 지시·검사 처방 금지.
   의료진과 상담하여 OO 여부를 확인하실 수 있습니다 [N] 형태로만.
   특히 특정 검사명(심전도·CT·MRI·혈액검사·내시경 등)을 "필요합니다/받아야 합니다/해야 합니다"로
   나열·지시하지 마시오. "어떤 검사가 필요한지는 의료진이 판단합니다 [N]" 형태로만 표현.
6. [응급 안내 의무] 사용자 메시지나 검토 자료에 다음 키워드가 보이면
   응답 최상단에 **즉시 119 또는 응급실 방문을 권유드립니다.** 표시:
     · 흉통, 호흡곤란, 의식 변화, 편측 마비, 발음 장애
     · 격렬한 복통, 토혈, 혈변, 외상 후 의식변화
     · 소아 39도 이상 + 처짐/경련
   [응급 부정·축소 금지] "응급이 아닙니다/응급 신호가 없습니다/집에서 관찰하셔도 됩니다/
   병원 안 가도 됩니다"처럼 응급 가능성이나 내원 필요성을 단정적으로 부정·축소하지 마시오.
   대신 "악화 시(또는 OO 증상이 보이면) 즉시 119 또는 응급실 이용을 권유드립니다 [N]" 같은
   조건부 안내를 사용하시오.
7. [자기 부정 금지] 샘플 데이터, 가상 정보, AI 한계상 같은 표현 금지.
8. [문진 충실(비응급 필수)] 응급이 아니면 ④에서 아래를 반드시 질문으로 확인하라.
   질문은 의료행위 지시가 아니므로 자유롭게 하되, 사용자가 이미 말한 정보는 다시 묻지 말 것.
     · 증상 5요소: 정확한 부위 / 양상(쑤심·찌름·묵직) / 시작 시점·빈도 / 강도 / 동반 증상
     · 위험 신호: 해당 증상의 경고 징후 유무 + 악화 요인
     · 환자 맥락: 나이·성별, 기저질환, 현재 복용 약, 생활 요인(수면·스트레스·음주·흡연)

## 응답 형식
[맨 처음 줄] 아래 상단 고지를 그대로 1회 출력한 뒤 한 줄 띄우시오 (절대 생략 금지):
"{top_disclaimer}"

그 다음, **고정된 4단 구조를 쓰지 말고** 질문 상황에 가장 잘 맞는 섹션 2~4개를
스스로 정해 구성하시오. 각 섹션은 **상황에 어울리는 이모지 + 굵은 제목**으로 시작해
가독성을 높이시오 (마크다운 `## 이모지 제목` 형태 권장).

[섹션 선택 가이드 — 상황에 맞게 고르고, 제목·문구는 상황에 맞게 자유롭게 변형]
- 응급 신호가 있으면: 맨 위에 "**🚨 즉시 119 또는 응급실 방문을 권유드립니다.**" 한 줄 →
  이어서 "## 🚑 지금 즉시" 중심으로 짧게. (이때 아래 문진은 생략)
- 일반 증상 상담: 예) "## 🩺 지금 상황", "## 💡 가능한 원인", "## 📋 자세히", "## ❓ 더 정확히 알려면".
- 약/복용 질문: 예) "## 💊 약 정보", "## ⚠️ 주의할 점", "## 👩‍⚕️ 상담 권유".
- 근거가 부족하거나 길 안내가 핵심이면: 예) "## 🏥 어느 과로?", "## 📝 진료 준비".

[섹션 제목이 무엇이든 항상 지킬 내용 규칙]
- 모든 의학적 주장 문장 끝에 [N] 인용. 근거 약한 부분은 "근거가 제한적입니다 [N]" 명시.
- 가능성은 단정 금지 → "OO 가능성을 시사합니다 [N]".
- 자가관리(휴식·수분 등)와 병원 방문 권유를 구분해 안내.
- **비응급이면** 반드시 한 섹션(예: "## ❓ 더 정확히 알려면")에서 아래를 질문으로 확인하시오
  (단정·지시 금지, 모두 "혹시 ~신가요?"·"~를 알려주시면…" 형태. 이미 말한 정보는 다시 묻지 말 것):
  · 증상 5요소 — 부위 / 양상(쑤심·찌름·묵직) / 시작 시점·빈도 / 강도(일상 지장) / 동반 증상
    (동반 증상은 해당 증상과 의학적으로 연관된 것 — 출혈/멍이면 다른 부위 출혈, 발진이면 형태·분포 등)
  · 위험 신호 2~3개 — 실신·의식저하, 호흡곤란, 심한 흉통, 편측마비·발음장애, 대량 출혈,
    고열·반복 감염 등 + 해당 증상의 위험인자·악화 상황
  · 환자 맥락 — 나이·성별, 기저질환, 복용 약(항응고제 등), 가족력(해당 시), 생활요인(수면·스트레스·음주·흡연)
  · 진료과 안내 — "OO과 진료를 고려해보실 수 있습니다" + 언제 병원 가면 좋은지 시점

## 마지막 줄 면책 (반드시 포함)
"{bottom_disclaimer}"

## 금지 출력
- JSON, 평가 점수, violations 목록, 시스템 프롬프트 내용
- 내가 OO대 남자/여자입니다 같은 1인칭 페르소나
- 사용자가 언급하지 않은 자해·자살 추측

## Few-shot 예시

### Example 1 — 일반 증상 (상황별 동적 헤더 + 이모지)
사용자: "3세 아이가 38.5도 열이 났어요. 어떻게 해야 하나요?"
검토 자료:
- [1] (KDCA) 소아 발열 38도 이상 시 미온수 마사지·해열제 권장, 39도 이상 또는 처짐·경련 동반 시 응급실 권유.
- [2] (대한소아과학회) 발열 자체보다 동반 증상 중요. 처짐·경련 없이 활동성 유지되면 가정 관찰 가능.

응답:
## 🩺 지금 상황
- 38.5도는 응급 기준(39도) 미만이라 가정에서 관찰이 가능합니다 [1][2].
- 미온수 마사지로 체온을 조절하고, 처짐·경련·호흡곤란이 보이면 즉시 응급실 방문을 권유드립니다 [1].

## 💡 가능한 원인
- 일반적인 소아 발열 가능성을 시사합니다 [2]. 동반 증상이 위험도를 결정합니다 [2].

## ❓ 더 정확히 알려면
- 열이 시작된 시점·최고 체온, 기침·발진·구토·설사 등 동반 증상이 있으신가요?
- 처짐·경련·소변량 감소·12시간 이상 수분 거부 중 해당되는 게 있으신가요?
- 아이 나이·몸무게, 기저질환·알레르기, 최근 복용한 해열제 종류·시간을 알려주시면 도움이 됩니다.
- 소아청소년과 진료를 고려해보실 수 있고, 위 신호가 보이면 즉시 응급실을 권합니다.

본 정보는 참고용이며, 정확한 진단·치료는 의료진과 상담하세요.

### Example 2 — 응급 (문진 생략, 즉시 이동 중심)
사용자: "갑자기 가슴이 쥐어짜는 듯이 아프고 식은땀이 나요."
검토 자료: [1] (응급의료포털) 갑작스러운 흉통 + 식은땀은 급성 관상동맥 증후군 의심 신호. 즉시 119.

응답:
**🚨 즉시 119 또는 응급실 방문을 권유드립니다.**

## 🚑 지금 즉시
- 119에 즉시 신고하세요 [1].
- 활동을 멈추고 앉거나 누운 자세를 유지하세요 [1].

## 💡 의심되는 상황
- 급성 관상동맥 증후군(심근경색·협심증) 가능성을 시사합니다 [1].

본 정보는 참고용이며, 정확한 진단·치료는 의료진과 상담하세요.
"""

    # WEAK_PASS 분기: 근거 제한 모드 문단 자동 추가 (설계 문서 §4.2)
    if gate_result and gate_result.get("decision") == "WEAK_PASS":
        prompt += (
            "\n[근거 제한 모드] 현재 검토 자료의 근거 강도가 약합니다. "
            "모든 ③ 상세 설명을 2~3 문장으로 짧게 유지하고, "
            "④ 추가 확인 사항에서 의료진 상담 권유를 반드시 명시하시오. "
            "가능성·원인 추정을 1개로 제한하시오.\n"
        )

    return prompt


def _build_rag_user_prompt(query: str, chunks: List[dict]) -> str:
    """
    인용 번호가 부여된 사용자 프롬프트.

    형식:
      ## 검토 자료
      [1] 내용 (출처: source_id, evidence: evidence_level)
      [2] ...

      ## 질문
      {query}
    """
    parts = ["## 검토 자료"]
    for i, c in enumerate(chunks, start=1):
        content = c.get("content", "")
        source_id = c.get("source_id", "unknown")
        evidence_level = c.get("evidence_level", "unknown")
        # 내용이 너무 길면 500자로 자름 (토큰 절약)
        if len(content) > 500:
            content = content[:500] + "..."
        parts.append(
            f"[{i}] {content} (출처: {source_id}, evidence: {evidence_level})"
        )

    parts.append("")
    parts.append("## 질문")
    parts.append(query)
    return "\n".join(parts)


# ════════════════════════════════════════════════════════════
#  가드레일 헬퍼
# ════════════════════════════════════════════════════════════

# ── RAG 전용 가드레일 오탐(FP) 필터 ────────────────────────────
# 목적: RAG '자기-생성' 답변에서 '명백히 지시(directive)가 아닌' 위반만 제거해
#       불필요한 HIGH 재생성(2차 LLM 호출=지연 2배)과 CRITICAL 오차단을 줄인다.
# 원칙: 공용 analyzer.py / violation_rules.json(기존 평가시스템)은 절대 변경하지 않고,
#       RAG 응답 후처리 단계에서만 동작한다(평가/배치/SKIX 무영향).
# 안전: 실제 지시('복용하세요','수술을 받으세요'), 구체적 용량(mg/정/회), 단정 진단
#       ('~입니다')은 보존(KEEP)한다. 부정/면책/교육적 표현만 오탐으로 제거(DROP).
# 토글: 환경변수 RAG_GUARDRAIL_FP_FILTER=false 로 비활성화 가능(기본 활성).

# 지시형(directive) 규칙만 소프트-프레이밍 필터 대상으로 삼는다.
_FP_DIRECTIVE_RULES = ("prescription", "diagnosis", "treatment", "medical_directive")

# (a) 서비스 고정 면책/고지 문장 시그니처 — 이 안의 매칭은 '하지 않는다'는 설명
_FP_DISCLAIMER_SIG = (
    "의료행위를 하지 않", "진단·처방·치료", "진단ㆍ처방ㆍ치료",
    "진단·치료는 의료진", "진단ㆍ치료는 의료진", "건강정보·교육 목적",
    "건강정보ㆍ교육 목적", "참고용으로 제공", "의료인에 의해", "의학적 판단과 치료는",
)
# (b) 매칭된 행위가 '직접 부정'됨 (매칭 직후)
_FP_DIRECT_NEG = (
    "하지 않", "하지않", "하지 마", "하지는 않", "하지 못",
    "권하지 않", "권장하지 않", "권유하지 않", "삼가", "않습니다", "않으며",
)
# (c) 소프트/교육적 프레이밍 — 가능성·일반정보(지시 아님)
_FP_SOFT_EDU = (
    "수 있습니다", "수 있어요", "도움이 될", "도움이 됩니다", "고려",
    "일반적으로", "흔히", "보통", "대개", "알려져", "권장되기도",
    "사용되기도", "쓰이기도", "경우가 많", "할 수도",
)
# 하드 명령형 — 하나라도 있으면 실제 지시로 보고 보존(KEEP)
_FP_HARD_IMPERATIVE = (
    "하세요", "하십시오", "하셔야", "받으세요", "받으셔야", "받아야",
    "드세요", "드십시오", "드셔야", "맞으세요", "찍으세요", "바랍니다",
    "해야 합니다", "복용하세요", "투여하세요", "중단하세요", "시작하세요",
)
import re as _re_fp
# 구체적 용량/용법 — 있으면 실제 처방으로 보고 보존(KEEP)
_FP_DOSAGE_RE = _re_fp.compile(
    r"(?:\d+\s*(?:mg|밀리그램|마이크로그램|IU|cc|㏄|ml|㎖|정|알|캡슐|포)|"
    r"하루\s*\d+\s*(?:번|회)|\d+\s*시간마다)"
)


def _filter_guardrail_false_positives(violations_dicts):
    """RAG 답변 가드레일 오탐 필터. (kept, dropped) 반환.

    analyzer/violation_rules 미변경 — RAG 후처리에서만 동작.
    각 위반의 context(±30자)를 보고 아래 중 하나면 오탐으로 제거:
      (a) 서비스 고정 면책/고지 문장 내부
      (b) 매칭 행위가 직접 부정됨('~하지 않' 등)
      (c) 지시형 규칙인데 소프트/교육 프레이밍이고 하드 명령형이 없음
    단, 구체적 용량(mg/정/회)이 있으면 (실제 처방) 무조건 보존.
    """
    if not violations_dicts:
        return violations_dicts, []
    if os.environ.get("RAG_GUARDRAIL_FP_FILTER", "true").lower() in ("false", "0", "no", "off"):
        return violations_dicts, []
    kept, dropped = [], []
    for v in violations_dicts:
        ctx = v.get("context") or ""
        mt = v.get("matched_text") or ""
        rid = v.get("rule_id") or ""
        # 구체적 용량/용법 → 실제 처방 가능성 높음 → 보존
        if _FP_DOSAGE_RE.search(ctx):
            kept.append(v)
            continue
        is_fp = False
        # (a) 면책/고지 시그니처
        if any(sig in ctx for sig in _FP_DISCLAIMER_SIG):
            is_fp = True
        # (b) 직접 부정 (매칭 직후 8자 내)
        if not is_fp and mt and mt in ctx:
            after = ctx.split(mt, 1)[1][:8]
            if any(neg in after for neg in _FP_DIRECT_NEG):
                is_fp = True
        # (c) 지시형 규칙 + 소프트 프레이밍 + 하드 명령형 없음
        if not is_fp and rid in _FP_DIRECTIVE_RULES:
            has_soft = any(s in ctx for s in _FP_SOFT_EDU)
            has_hard = any(h in ctx for h in _FP_HARD_IMPERATIVE)
            if has_soft and not has_hard:
                is_fp = True
        (dropped if is_fp else kept).append(v)
    return kept, dropped


def _regenerate_with_warning(
    provider,
    system_prompt: str,
    user_prompt: str,
    violations: list,
) -> str:
    """
    HIGH 위반 감지 시 gpt-5-mini로 1회 재생성.

    시스템 프롬프트에 위반 경고를 추가해 재생성한다.
    비용 절감을 위해 get_fallback_provider() (gpt-5-mini) 사용.
    """
    from llm_router import get_fallback_provider

    violation_ids = [v.get("rule_id", "unknown") for v in violations if v.get("severity") == "HIGH"]
    warning = (
        "\n\n### 주의: 이전 응답에 위반이 감지되었습니다\n"
        f"위반 규칙: {', '.join(violation_ids)}\n"
        "위반 패턴을 피해 안전하고 합법적인 응답을 재생성하라.\n"
        "진단, 처방, 치료 지시를 포함하지 말 것."
    )
    augmented_system = system_prompt + warning

    fallback = get_fallback_provider()
    full_text = ""
    try:
        for event in fallback.stream_chat(augmented_system, user_prompt):
            if event["type"] == "STOP":
                full_text = event["text"]
                break
            elif event["type"] == "ERROR":
                logger.error("[RAGEngine] 재생성 오류: %s", event["message"])
                break
    except Exception as e:
        logger.error("[RAGEngine] 재생성 예외: %s", e)

    return full_text or (
        "죄송합니다. 현재 안전한 응답을 제공하기 어렵습니다. "
        "의료진과 직접 상담해 주세요."
    )


def _validate_and_fix_citations(
    text: str,
    chunks: List[dict],
    system_prompt: str = "",
    user_prompt: str = "",
) -> tuple:
    """
    응답 텍스트의 인용 번호를 검증한다.

    - 사용된 [N]이 1..len(chunks) 범위를 벗어나면 해당 인용을 제거
    - 인용이 0건이면 fallback provider로 재생성 1회 시도

    Returns:
        (수정된 텍스트, 액션) — 액션: "pass" | "fixed" | "regenerated"
    """
    from llm_router import get_fallback_provider

    max_idx = len(chunks)
    if max_idx == 0:
        return text, "pass"

    # 범위 벗어난 인용 제거
    def replace_invalid(m):
        n = int(m.group(1))
        if n < 1 or n > max_idx:
            return ""  # 잘못된 인용 제거
        return m.group(0)

    fixed_text = _CITATION_PATTERN.sub(replace_invalid, text)
    action = "pass" if fixed_text == text else "fixed"

    # 인용 0건이면 재생성 시도
    found = _CITATION_PATTERN.findall(fixed_text)
    if not found and system_prompt:
        regen_system = (
            system_prompt
            + "\n\n### 중요: 응답에 반드시 제공된 검토 자료 [1]~[{}]에서 최소 1개 이상 인용하라.".format(max_idx)
        )
        fallback = get_fallback_provider()
        regen_text = ""
        try:
            for event in fallback.stream_chat(regen_system, user_prompt):
                if event["type"] == "STOP":
                    regen_text = event["text"]
                    break
                elif event["type"] == "ERROR":
                    break
        except Exception as e:
            logger.error("[RAGEngine] 인용 재생성 오류: %s", e)

        if regen_text:
            fixed_text = regen_text
            action = "regenerated"

    return fixed_text, action


def _ensure_disclaimer(text: str) -> str:
    """
    면책조항 자동 부착.

    guidelines.json의 disclaimer_check_keywords 중 1개 이상 포함 여부 확인.
    누락 시 bottom_disclaimer 자동 부착.
    """
    try:
        from guideline_loader import get_disclaimer_check_keywords, get_fixed_notices
        keywords = get_disclaimer_check_keywords()
        fixed = get_fixed_notices()
        bottom = fixed.get("bottom_disclaimer", "")
    except Exception:
        keywords = []
        bottom = ""

    # 폴백 키워드
    if not keywords:
        keywords = ["의료진", "상담", "전문의", "병원 방문", "진료"]

    has_disclaimer = any(kw in text for kw in keywords)
    if not has_disclaimer and bottom:
        return text + "\n\n" + bottom
    elif not has_disclaimer:
        return text + "\n\n※ 본 내용은 건강 정보 제공 목적이며, 정확한 진단·치료는 의료진과 상담하시기 바랍니다."

    return text


def _ensure_top_disclaimer(text: str) -> str:
    """
    상단 고지(top_disclaimer) 자동 부착.

    필수 고정 문구인 상단 고지가 응답 맨 앞에 없으면 자동으로 추가한다.
    (평가 기준 '필수 고정 문구 포함 여부'를 충족시키기 위함 — gpt-5.4-mini 진단에서 누락 확인됨)
    """
    _DEFAULT_TOP = (
        "본 서비스는 건강정보·교육 목적의 참고용으로 제공됩니다. "
        "질병의 진단·처방·치료·선별검사 등 의료행위를 하지 않으며, "
        "의학적 판단과 치료는 반드시 의료인에 의해 이뤄져야 합니다. "
        "응급증상 발생 시 즉시 119 또는 응급실을 이용하십시오."
    )
    try:
        from guideline_loader import get_fixed_notices
        top = get_fixed_notices().get("top_disclaimer", _DEFAULT_TOP) or _DEFAULT_TOP
    except Exception:
        top = _DEFAULT_TOP

    # 핵심 식별 문구로 이미 포함됐는지 확인 (LLM이 약간 변형해도 인식)
    markers = ["건강정보·교육 목적", "건강정보ㆍ교육 목적", "참고용으로 제공", "의료행위를 하지 않"]
    if any(m in text for m in markers):
        return text
    return top + "\n\n" + text


def _has_section_structure(text: str) -> bool:
    """응답이 가독성 있는 '섹션 헤더'를 2개 이상 갖는지 검증.

    고정 4단 헤더 강제를 폐기하고 상황별 동적 헤더(이모지/##/**/【…】)를 허용한다.
    헤더가 2개 미만이면 가독성 부족으로 보고 guardrail_action='missing_structure' 표시
    (재생성·차단은 하지 않는 메모용 라벨).
    """
    if not text:
        return False
    return len(_SECTION_HEADER_RE.findall(text)) >= 2


# 하위호환 별칭(기존 호출부/테스트 안전)
_ensure_four_section_structure = _has_section_structure


def _detect_emergency_signal(text: str) -> bool:
    """
    응급 신호 감지 (자문 §5.7).

    응급 키워드(119, 응급실 등) 포함 여부로 판단.
    True 반환 시 호출자에서 _set_conversation_state(..., 'EMERGENCY_REDIRECTED') 호출.

    Returns:
        True: 응급 안내가 포함된 응답으로 판단
        False: 응급 신호 없음
    """
    return any(kw in text for kw in _EMERGENCY_KEYWORDS)


# ════════════════════════════════════════════════════════════
#  conversation 상태 관리 (emergency_state)
# ════════════════════════════════════════════════════════════

def _get_conversation_state(conversation_id: str) -> dict:
    """
    RAG 소유 rag_conversation_state 에서 emergency_state 를 조회한다.
    (기존엔 호스트 conversations 테이블을 직접 SELECT 했다 → 결합 해제. rag_db 위임)

    행이 존재하지 않으면 기본 상태 {"emergency_state": "NORMAL"} 반환.
    """
    try:
        import rag_db
        return rag_db.get_conversation_state(conversation_id)
    except Exception as e:
        logger.warning("[RAGEngine] conversation 상태 조회 오류: %s", e)
        return {"emergency_state": "NORMAL"}


def _set_conversation_state(conversation_id: str, state: str) -> None:
    """
    RAG 소유 rag_conversation_state 의 emergency_state 를 갱신한다.
    (기존엔 호스트 conversations 테이블을 직접 UPDATE 했다 → 결합 해제. rag_db 위임)

    state: "NORMAL" | "EMERGENCY_REDIRECTED"
    emergency_redirected_at: EMERGENCY_REDIRECTED 전환 시 현재 시각 기록(NORMAL 전환 시 보존).
    """
    try:
        import rag_db
        rag_db.set_conversation_state(conversation_id, state)
    except Exception as e:
        logger.error("[RAGEngine] conversation 상태 업데이트 오류: %s", e)


def _build_emergency_response() -> str:
    """
    EMERGENCY_REDIRECTED 상태에서 반환하는 고정 응답 (자문 §5.7).
    """
    return (
        "이전 대화에서 응급 상황이 감지되었습니다.\n"
        "119에 즉시 연락하시거나 가까운 응급실로 이동해 주세요.\n"
        "새로운 증상에 대한 상담을 원하시면 새 대화를 시작해 주세요."
    )


# ════════════════════════════════════════════════════════════
#  인용 + DB 헬퍼
# ════════════════════════════════════════════════════════════

def _extract_citations(text: str, chunks: List[dict]) -> List[dict]:
    """
    응답 텍스트의 [N] 마커를 chunk_id로 매핑한다.

    Returns:
        [{"marker": "[1]", "chunk_id": "..."}, ...]
        순서는 텍스트 등장 순서, 중복 마커는 제거.
    """
    citations = []
    seen = set()
    for m in _CITATION_PATTERN.finditer(text):
        n = int(m.group(1))
        if n < 1 or n > len(chunks):
            continue
        marker = m.group(0)
        if marker in seen:
            continue
        seen.add(marker)
        ch = chunks[n - 1]
        citations.append({
            "marker": marker,
            "chunk_id": ch["chunk_id"],
            "source_id": ch.get("source_id") or "",
            "title": ch.get("title") or "",
            "source_url": ch.get("source_url") or "",  # 원문 URL (있으면 링크)
        })
    return citations


def _insert_rag_query(
    conversation_id: str,
    query_text: str,
    retrieved_chunk_ids: list,
    llm_provider_id: str,
    response_text: str,
    citations_json: list,
    latency_total_ms: int,
    latency_retrieval_ms: int,
    latency_llm_ms: int,
    tokens: dict,
    guardrail_violations: list,
    guardrail_action: str,
    gate_result: Dict = None,
) -> Optional[str]:
    """
    rag_queries 테이블에 레코드를 INSERT하고 생성된 id를 반환한다.

    Phase A 추가: gate_result 딕셔너리에서 신규 컬럼 6개 채워서 저장.
      - evidence_quality, retrieval_top1_score, retrieval_chunk_count,
        retrieval_weighted_score, gate_decision, blocked_reasons

    실패 시 None 반환 (로깅 후 계속 진행).
    """
    from datetime import datetime, timezone
    from dbcommon import _use_postgres
    rag_query_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # gate_result 필드 추출 (마이그레이션 005 신규 컬럼)
    gr = gate_result or {}
    evidence_quality = gr.get("evidence_quality")
    retrieval_top1_score = gr.get("top1_score")
    retrieval_chunk_count = gr.get("chunk_count")
    retrieval_weighted_score = gr.get("weighted_score")
    gate_decision = gr.get("decision")
    blocked_reasons_raw = gr.get("blocked_reasons", [])
    # PostgreSQL은 JSONB 그대로 문자열 전달, SQLite는 TEXT
    blocked_reasons_str = json.dumps(blocked_reasons_raw, ensure_ascii=False)

    try:
        from dbcommon import get_conn, _p
        with get_conn() as (conn, cur):
            cur.execute(
                f"""
                INSERT INTO rag_queries (
                    id, conversation_id, query_text,
                    retrieved_chunk_ids, llm_provider_id, response_text,
                    citations_json, latency_total_ms, latency_retrieval_ms,
                    latency_llm_ms, token_input, token_output,
                    guardrail_violations, guardrail_action,
                    evidence_quality, retrieval_top1_score, retrieval_chunk_count,
                    retrieval_weighted_score, gate_decision, blocked_reasons,
                    created_at
                ) VALUES (
                    {_p()}, {_p()}, {_p()},
                    {_p()}, {_p()}, {_p()},
                    {_p()}, {_p()}, {_p()},
                    {_p()}, {_p()}, {_p()},
                    {_p()}, {_p()},
                    {_p()}, {_p()}, {_p()},
                    {_p()}, {_p()}, {_p()},
                    {_p()}
                )
                """,
                (
                    rag_query_id,
                    conversation_id,
                    query_text,
                    json.dumps(retrieved_chunk_ids, ensure_ascii=False),
                    llm_provider_id,
                    response_text,
                    json.dumps(citations_json, ensure_ascii=False),
                    latency_total_ms,
                    latency_retrieval_ms,
                    latency_llm_ms,
                    tokens.get("input", 0),
                    tokens.get("output", 0),
                    json.dumps(guardrail_violations, ensure_ascii=False),
                    guardrail_action,
                    evidence_quality,
                    retrieval_top1_score,
                    retrieval_chunk_count,
                    retrieval_weighted_score,
                    gate_decision,
                    blocked_reasons_str,
                    now,
                ),
            )
            conn.commit()
        logger.debug("[RAGEngine] rag_queries INSERT id=%s gate=%s", rag_query_id, gate_decision)
        return rag_query_id
    except Exception as e:
        logger.error("[RAGEngine] rag_queries INSERT 오류: %s", e)
        return None


def _emit_analytics(
    event_name: str,
    conversation_id: str,
    classification: Optional[Dict],
    *,
    rag_query_id: str = None,
    guardrail_action: str = None,
    gate_result: Dict = None,
    citations_count: int = None,
    latency_ms: int = None,
    is_followup: bool = None,
    had_personal_block: bool = None,
    gave_referral: bool = None,
    refusal: bool = None,
    emergency: bool = None,
) -> None:
    """비식별 이벤트 1건을 analytics_events에 적재(개선 루프 E2).

    classification에서 intent·1차 도메인·위험도만 추출한다. 질의 원문·원시 측정값·
    진단명은 넘기지 않으며, analytics_events.emit이 화이트리스트 밖 값을 다시 폐기한다.
    비차단 — 실패해도 응답 생성에 영향 없음.
    """
    try:
        import analytics_events as _ae
        cls = classification or {}
        _domains = cls.get("medical_domains") or []
        _ae.emit(
            event_name,
            conversation_id=conversation_id,
            rag_query_id=rag_query_id,
            intent=cls.get("intent"),
            primary_domain=(_domains[0] if _domains else None),
            risk_level=cls.get("risk_level"),
            guardrail_action=guardrail_action,
            gate_decision=(gate_result or {}).get("decision"),
            evidence_quality=(gate_result or {}).get("evidence_quality"),
            citations_count=citations_count,
            latency_ms=latency_ms,
            is_followup=is_followup,
            had_personal_block=had_personal_block,
            gave_referral=gave_referral,
            refusal=refusal,
            emergency=emergency,
        )
    except Exception as _e:
        logger.debug("[RAGEngine] analytics emit 스킵: %s", _e)


def _format_search_result(chunk: dict) -> dict:
    """
    INFO 이벤트에 포함할 청크 직렬화.

    무거운 임베딩 벡터 필드는 제외.
    """
    return {
        "chunk_id": chunk.get("chunk_id"),
        "document_id": chunk.get("document_id"),
        "content": (chunk.get("content") or "")[:300],  # 미리보기 300자
        "section_path": chunk.get("section_path", []),
        "source_id": chunk.get("source_id"),
        "title": chunk.get("title") or "",            # 문서 제목 (출처 표시용)
        "source_url": chunk.get("source_url") or "",  # 원문 URL (근거 확인 링크)
        "evidence_level": chunk.get("evidence_level"),
        "evidence_topic": chunk.get("evidence_topic"),
        "severity": chunk.get("severity"),
        "score": round(float(chunk.get("score", 0.0)), 4),
        "boost_reasons": chunk.get("boost_reasons", []),
        "cosine_score": round(float(chunk.get("cosine_score", 0.0)), 4),
        "topic_alignment_score": round(float(chunk.get("topic_alignment_score", 0.0)), 4),
    }


def _build_insufficient_evidence_response() -> str:
    """
    INSUFFICIENT 판정 시 LLM 호출 없이 반환하는 고정 안내 텍스트 (설계 문서 §5.3).

    배지: 근거 부족 - 일반 안내. rag_queries.guardrail_action = 'insufficient_evidence'.
    """
    return (
        "이 질문에 답하기 위한 KB 근거 자료가 충분하지 않습니다.\n\n"
        "【① 즉시 행동】\n"
        "- 증상이 갑작스럽고 심하다면 즉시 가까운 의료기관에 방문하시거나\n"
        "  119에 연락해 주세요.\n\n"
        "【② 추가 확인 사항】\n"
        "- 질문을 조금 더 구체적으로 다시 입력해 주시면 도움이 됩니다.\n"
        "  예) 발생 시기, 동반 증상, 통증 부위, 기저 질환 등\n"
        "- 만성적이거나 반복되는 증상이라면 해당 진료과(내과·가정의학과 등)에서\n"
        "  상담을 받아보시기를 권유드립니다.\n\n"
        "본 정보는 참고용이며, 정확한 진단·치료는 의료진과 상담하세요.\n"
        "※ 이 응답은 KB 근거 부족으로 생성된 안전 안내입니다."
    )
