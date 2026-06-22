"""admin_routes.py — RAG 운영 어드민 집계 (읽기 전용).

rag_queries + response_feedback 를 집계해 답변속도·토큰·대화통계·최근쿼리·프롬프트를
JSON 으로 제공한다. 호출 측 = 비밀번호 보호 admin 대시보드(서버-대-서버, X-Admin-Secret).

이식성:
- created_at 은 ISO8601 TEXT → 구간 필터는 ISO 컷오프 파라미터, 일자 버킷은 Python str()[:10].
- dbcommon 커서는 PG=RealDictCursor / SQLite=sqlite3.Row → **행은 dict-like**.
  따라서 행 접근은 정수 인덱스가 아니라 **컬럼명**으로(집계는 alias). (정수 인덱스는 PG에서 KeyError.)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs

FX_KRW = float(os.environ.get("ADMIN_FX_KRW", "1550"))
PRICE_IN = float(os.environ.get("ADMIN_PRICE_IN_USD_PER_M", "0.30"))    # 추정 단가($/1M)
PRICE_OUT = float(os.environ.get("ADMIN_PRICE_OUT_USD_PER_M", "1.20"))  # 실제 단가로 교체


def _cost_krw(tin, tout) -> float:
    usd = (float(tin or 0) * PRICE_IN + float(tout or 0) * PRICE_OUT) / 1_000_000.0
    return round(usd * FX_KRW, 1)


def _i(v) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


KST = timezone(timedelta(hours=9))


def _kst_str(iso, fmt="%Y-%m-%d %H:%M:%S") -> str:
    """저장된 UTC ISO created_at → KST 문자열. (created_at 은 datetime.now(utc).isoformat())"""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime(fmt)
    except Exception:
        return str(iso)


class AdminRoutesMixin:
    """RagHandler 에 믹스인. self._send_json / self._send_error / self.headers 사용."""

    def _admin_ok(self) -> bool:
        secret = os.environ.get("ADMIN_SECRET")
        if not secret:
            return True  # 미설정 = 개방(로컬 전용). 운영은 반드시 ADMIN_SECRET 설정.
        return self.headers.get("X-Admin-Secret") == secret

    def _admin_days(self, parsed) -> int:
        try:
            d = int(parse_qs(parsed.query).get("days", ["30"])[0])
        except Exception:
            d = 30
        return max(1, min(d, 365))

    def _admin_cutoff(self, days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # ── 요약 KPI ──────────────────────────────────────────────
    def _rag_admin_summary(self, parsed):
        if not self._admin_ok():
            return self._send_error(403, "admin secret 필요")
        days = self._admin_days(parsed)
        cutoff = self._admin_cutoff(days)
        from dbcommon import get_conn, _p
        out = {"days": days, "fx_krw": FX_KRW,
               "price_in_usd_per_m": PRICE_IN, "price_out_usd_per_m": PRICE_OUT}
        try:
            with get_conn() as (conn, cur):
                cur.execute(
                    f"""SELECT count(*) AS n,
                               coalesce(avg(latency_total_ms),0)     AS avg_total,
                               coalesce(max(latency_total_ms),0)     AS max_total,
                               coalesce(avg(latency_retrieval_ms),0) AS avg_ret,
                               coalesce(avg(latency_llm_ms),0)       AS avg_llm,
                               coalesce(sum(token_input),0)          AS sum_in,
                               coalesce(sum(token_output),0)         AS sum_out,
                               coalesce(avg(token_input),0)          AS avg_in,
                               coalesce(avg(token_output),0)         AS avg_out
                        FROM rag_queries WHERE created_at >= {_p()}""",
                    (cutoff,))
                r = cur.fetchone()
                n = _i(r["n"])
                tin, tout = _i(r["sum_in"]), _i(r["sum_out"])
                avg_in, avg_out = float(r["avg_in"] or 0), float(r["avg_out"] or 0)
                out.update({
                    "queries": n,
                    "latency_ms": {"avg_total": round(float(r["avg_total"] or 0)),
                                   "max_total": round(float(r["max_total"] or 0)),
                                   "avg_retrieval": round(float(r["avg_ret"] or 0)),
                                   "avg_llm": round(float(r["avg_llm"] or 0))},
                    "tokens": {"sum_in": tin, "sum_out": tout, "sum_total": tin + tout,
                               "avg_in": round(avg_in), "avg_out": round(avg_out)},
                    "cost_krw_est": {"total": _cost_krw(tin, tout),
                                     "per_query": _cost_krw(avg_in, avg_out)},
                })
                fb = {"up": 0, "down": 0}
                try:
                    cur.execute(
                        f"""SELECT rating, count(*) AS cnt FROM response_feedback
                            WHERE created_at >= {_p()} GROUP BY rating""", (cutoff,))
                    for row in cur.fetchall():
                        if row["rating"] in fb:
                            fb[row["rating"]] = _i(row["cnt"])
                except Exception:
                    pass
                out["feedback"] = fb
        except Exception as e:
            return self._send_error(500, f"집계 실패: {type(e).__name__}: {e}")
        return self._send_json(200, out)

    # ── 구간별(일자) 시계열 ───────────────────────────────────
    def _rag_admin_timeseries(self, parsed):
        if not self._admin_ok():
            return self._send_error(403, "admin secret 필요")
        days = self._admin_days(parsed)
        cutoff = self._admin_cutoff(days)
        from dbcommon import get_conn, _p
        buckets = {}
        try:
            with get_conn() as (conn, cur):
                cur.execute(
                    f"""SELECT created_at, token_input, token_output, latency_total_ms
                        FROM rag_queries WHERE created_at >= {_p()}
                        ORDER BY created_at""", (cutoff,))
                for row in cur.fetchall():
                    day = _kst_str(row["created_at"], "%Y-%m-%d")  # KST 일자 버킷
                    b = buckets.setdefault(day, {"queries": 0, "in": 0, "out": 0, "lat_sum": 0})
                    b["queries"] += 1
                    b["in"] += _i(row["token_input"])
                    b["out"] += _i(row["token_output"])
                    b["lat_sum"] += _i(row["latency_total_ms"])
        except Exception as e:
            return self._send_error(500, f"시계열 실패: {type(e).__name__}: {e}")
        series = []
        for day in sorted(buckets):
            b = buckets[day]
            series.append({"date": day, "queries": b["queries"],
                           "tokens_in": b["in"], "tokens_out": b["out"],
                           "tokens_total": b["in"] + b["out"],
                           "avg_latency_ms": round(b["lat_sum"] / b["queries"]) if b["queries"] else 0,
                           "cost_krw_est": _cost_krw(b["in"], b["out"])})
        return self._send_json(200, {"days": days, "series": series})

    # ── 대화 통계(분포) ───────────────────────────────────────
    def _rag_admin_stats(self, parsed):
        if not self._admin_ok():
            return self._send_error(403, "admin secret 필요")
        days = self._admin_days(parsed)
        cutoff = self._admin_cutoff(days)
        from dbcommon import get_conn, _p

        def dist(cur, col):
            cur.execute(
                f"""SELECT {col} AS label, count(*) AS cnt FROM rag_queries
                    WHERE created_at >= {_p()} GROUP BY {col} ORDER BY count(*) DESC""",
                (cutoff,))
            res = []
            for row in cur.fetchall():
                lab = row["label"]
                res.append({"label": (lab if lab is not None else "(없음)"), "count": _i(row["cnt"])})
            return res
        try:
            with get_conn() as (conn, cur):
                out = {"days": days,
                       "evidence_quality": dist(cur, "evidence_quality"),
                       "gate_decision": dist(cur, "gate_decision"),
                       "guardrail_action": dist(cur, "guardrail_action")}
        except Exception as e:
            return self._send_error(500, f"통계 실패: {type(e).__name__}: {e}")
        return self._send_json(200, out)

    # ── 최근 쿼리(감사, 원문 포함) ────────────────────────────
    def _rag_admin_recent(self, parsed):
        if not self._admin_ok():
            return self._send_error(403, "admin secret 필요")
        try:
            limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
        except Exception:
            limit = 50
        limit = max(1, min(limit, 200))
        from dbcommon import get_conn, _p
        rows = []
        try:
            with get_conn() as (conn, cur):
                cur.execute(
                    f"""SELECT created_at, query_text, response_text, token_input, token_output,
                               latency_total_ms, latency_llm_ms, guardrail_action,
                               evidence_quality, gate_decision
                        FROM rag_queries ORDER BY created_at DESC LIMIT {_p()}""",
                    (limit,))
                for r in cur.fetchall():
                    ti, to = _i(r["token_input"]), _i(r["token_output"])
                    rows.append({
                        "created_at": str(r["created_at"]),
                        "created_kst": _kst_str(r["created_at"]),
                        "query": (r["query_text"] or "")[:500],
                        "answer": (r["response_text"] or "")[:8000],   # 전체(클릭 시 표시)
                        "token_in": ti, "token_out": to,
                        "latency_ms": _i(r["latency_total_ms"]),
                        "latency_llm_ms": _i(r["latency_llm_ms"]),
                        "guardrail_action": r["guardrail_action"],
                        "evidence_quality": r["evidence_quality"],
                        "gate_decision": r["gate_decision"],
                        "cost_krw_est": _cost_krw(ti, to),
                    })
        except Exception as e:
            return self._send_error(500, f"최근쿼리 실패: {type(e).__name__}: {e}")
        return self._send_json(200, {"limit": limit, "rows": rows})

    # ── 현재 시스템 프롬프트 ──────────────────────────────────
    def _rag_admin_prompt(self, parsed):
        if not self._admin_ok():
            return self._send_error(403, "admin secret 필요")
        try:
            from rag_engine import _build_rag_system_prompt
            text = _build_rag_system_prompt("샘플 질의(예: 혈압이 높게 나왔어요)", [])
        except Exception as e:
            text = f"(프롬프트 빌드 실패: {e})"
        model = os.environ.get("RAG_LLM_MODEL", "gpt-5.4-mini")
        effort = os.environ.get("LLM_REASONING_EFFORT", "minimal")
        return self._send_json(200, {"model": model, "reasoning_effort": effort,
                                     "system_prompt_sample": text})
