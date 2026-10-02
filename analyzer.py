"""
analyzer.py (루트 shim) — 4-B/B2
==================================
실제 구현은 packages/medical_shared/compliance_rules/analyzer.py 로 이동했다.
모듈 별칭 방식으로 sys.modules 에 등록해 런타임 패치 및 `import analyzer` 를
투명하게 지원한다.
"""
import sys as _sys
import importlib as _importlib

_impl = _importlib.import_module('packages.medical_shared.compliance_rules.analyzer')


def __getattr__(name):
    # 동시 import 경쟁: 이 shim 이 실행되는 동안 sys.modules 에서 shim 을 집어 간 다른 스레드는 모듈 잠금이
    # 풀린 뒤에도 교체 전 shim 객체를 받는다(CPython import.c 빠른 경로는 다시 조회하지 않는다). 그 객체에서
    # 찾는 이름은 구현으로 넘긴다. 이게 없어서 `from analyzer import ComplianceAnalyzer` 가 ImportError 를 내고
    # 가드레일이 검사 없이 통과했다(2026-09-29 dev 콜드스타트, tests/test_shim_import_race.py).
    return getattr(_impl, name)


_sys.modules['analyzer'] = _impl
_sys.modules[__name__] = _impl
