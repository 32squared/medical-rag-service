"""
guideline_loader.py (루트 shim) — 4-B/B2
==========================================
실제 구현은 packages/medical_shared/compliance_rules/guideline_loader.py 로 이동했다.
모듈 별칭 방식으로 sys.modules 에 등록한다.
"""
import sys as _sys
import importlib as _importlib

_impl = _importlib.import_module('packages.medical_shared.compliance_rules.guideline_loader')


def __getattr__(name):
    # 교체 전 shim 객체를 받은 동시 import 스레드도 구현을 보게 한다 — analyzer.py 주석 참고.
    return getattr(_impl, name)


_sys.modules['guideline_loader'] = _impl
_sys.modules[__name__] = _impl
