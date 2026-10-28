"""kb_collect — 카탈로그(kb_catalog) 기반 공인 기관 KB 자동 구축 패키지.

runner.run_sources() 가 진입점. 네트워크 라이브러리는 clients 안에서 지연 import 한다
(CI 의 안정 테스트는 requests 없이 돈다).
"""
