"""
마이헬스케어 P0 BFF (FastAPI) — 인증·동의검증·라우팅·RAG 프록시.

정본: docs/plan/23-p0-detailed-design.md. 기존 Python 자산(consent_db·account_db·
RAG 서비스)을 그대로 뒤에 두고, 엣지에서 본인인증·동의게이트를 선검증한다.
경계 불변: 원시값·진단명은 RAG 서비스 내부 결정엔진만, BFF 는 동의 판정 → 헤더만 전달.
"""
