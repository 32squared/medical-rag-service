"""admin_routes.py — RAG 운영 어드민 집계 (읽기 전용).

rag_queries + response_feedback 를 집계해 답변속도·토큰·대화통계·최근쿼리·프롬프트를
JSON 으로 제공한다. 호출 측 = 비밀번호 보호 admin 대시보드(서버-대-서버, X-Admin-Secret).

이식성: created_at 은 ISO8601 문자열 → 구간 필터는 ISO 컷오프 파라미터, 일자 버킷은
Python 측 str(created_at)[:10] 로 처리(PG/SQLite 공통, DB 날짜함수 미사용).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs

FX_KRW = float(os.environ.get("ADMIN_FX_KRW", "1550"))
PRICE_IN = float(os.environ.get("ADMIN_PRICE_IN_USD_PER_M", "0.30"))    # 추정 단가($/1M)
PRICE_OUT = float(os.environ.get("ADMIN_PRICE_OUT_USD_PER_M", "1.20"))  # 실제 단가로 교체


def _cost_krw(tin: float, tout: float) -> float:
    usd = (tin * PRICE_IN + tout * PRICE_OUT) / 1_000_000.0
    return round(usd * FX_KRW, 1)


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
                    f"""SELECT count(*),
                               coalesce(avg(latency_total_ms),0), coalesce(max(latency_total_ms),0),
                               coalesce(avg(latency_retrieval_ms),0), coalesce(avg(latency_llm_ms),0),
                               coalesce(sum(token_input),0), coalesce(sum(token_output),0),
                               coalesce(avg(token_input),0), coalesce(avg(token_output),0)
                        FROM rag_queries WHERE created_at >= {_p()}""",
                    (cutoff,))
                r = cur.fetchone()
                n = int(r[0] or 0)
                tin, tout = int(r[5] or 0), int(r[6] or 0)
                out.update({
                    "queries": n,
                    "latency_ms": {"avg_total": round(float(r[1] or 0)),
                                   "max_total": round(float(r[2] or 0)),
                                   "avg_retrieval": round(float(r[3] or 0)),
                                   "avg_llm": round(float(r[4] or 0))},
                    "tokens": {"sum_in": tin, "sum_out": tout, "sum_total": tin + tout,
                               "avg_in": round(float(r[7] or 0)), "avg_out": round(float(r[8] or 0))},
                    "cost_krw_est": {"total": _cost_krw(tin, tout),
                                     "per_query": _cost_krw(r[7] or 0, r[8] or 0)},
                })
                # 피드백 (있으면)
                fb = {"up": 0, "down": 0}
                try:
                    cur.execute(
                        f"""SELECT rating, count(*) FROM response_feedback
                            WHERE created_at >= {_p()} GROUP BY rating""", (cutoff,))
                    for rating, c in cur.fetchall():
                        if rating in fb:
                            fb[rating] = int(c)
                except Exception:
                    pass
                out["feedback"] = fb
        except Exception as e:
            return self._send_error(500, f"집계 실패: {e}")
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
                for ca, ti, to, lat in cur.fetchall():
                    day = str(ca)[:10]
                    b = buckets.setdefault(day, {"date": day, "queries": 0, "in": 0,
                                                 "out": 0, "lat_sum": 0})
                    b["queries"] += 1
                    b["in"] += int(ti or 0)
                    b["out"] += int(to or 0)
                    b["lat_sum"] += int(lat or 0)
        except Exception as e:
            return self._send_error(500, f"시계열 실패: {e}")
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
                f"""SELECT {col}, count(*) FROM rag_queries
                    WHERE created_at >= {_p()} GROUP BY {col} ORDER BY count(*) DESC""",
                (cutoff,))
            return [{"label": (k if k is not None else "(없음)"), "count": int(c)}
                    for k, c in cur.fetchall()]
        try:
            with get_conn() as (conn, cur):
                out = {"days": days,
                       "evidence_quality": dist(cur, "evidence_quality"),
                       "gate_decision": dist(cur, "gate_decision"),
                       "guardrail_action": dist(cur, "guardrail_action")}
        except Exception as e:
            return self._send_error(500, f"통계 실패: {e}")
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
                    rows.append({
                        "created_at": str(r[0]),
                        "query": (r[1] or "")[:500],
                        "answer": (r[2] or "")[:1200],
                        "token_in": int(r[3] or 0), "token_out": int(r[4] or 0),
                        "latency_ms": int(r[5] or 0), "latency_llm_ms": int(r[6] or 0),
                        "guardrail_action": r[7], "evidence_quality": r[8],
                        "gate_decision": r[9],
                        "cost_krw_est": _cost_krw(r[3] or 0, r[4] or 0),
                    })
        except Exception as e:
            return self._send_error(500, f"최근쿼리 실패: {e}")
        return self._send_json(200, {"limit": limit, "rows": rows})

    # ── 현재 시스템 프롬프트 ──────────────────────────────────
    def _rag_admin_prompt(self, parsed):
        if not self._admin_ok():
            return self._send_error(403, "admin secret 필요")
        text = ""
        try:
            from rag_engine import _build_rag_system_prompt
            text = _build_rag_system_prompt("샘플 질의(예: 혈압이 높게 나왔어요)", [])
        except Exception as e:
            text = f"(프롬프트 빌드 실패: {e})"
        model = os.environ.get("RAG_LLM_MODEL", "gpt-5.4-mini")
        effort = os.environ.get("LLM_REASONING_EFFORT", "minimal")
        return self._send_json(200, {"model": model, "reasoning_effort": effort,
                                     "system_prompt_sample": text})
