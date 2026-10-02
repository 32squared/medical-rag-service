"""
루트 shim 동시 import 경쟁 — 가드레일 fail-open 회귀.

2026-09-29 dev rev medical-rag-dev-00066-tql 배포 직후 병렬 요청 2건 중 하나가
`cannot import name 'ComplianceAnalyzer' from 'analyzer' (/app/analyzer.py)` 로 가드레일을 건너뛰었다
(generate_response 의 except → action=error, 검사 없이 답변 전달).

shim(analyzer.py 등)은 실행 중에 sys.modules 의 자기 자리를 구현 모듈로 바꾼다. 그 사이 다른 스레드가
같은 이름을 import 하면 CPython 빠른 경로(import.c import_ensure_initialized)가 sys.modules 에서 shim 을
집은 뒤 모듈 잠금이 풀리길 기다렸다가, 바뀐 구현이 아니라 처음 집은 shim 을 돌려준다. rag_engine 은 첫
요청 때 적재되고 analyzer shim 은 첫 가드레일 호출 때 처음 실행되므로, 새 인스턴스의 첫 동시 요청에서 난다.

이 테스트는 그 순서를 결정적으로 만든다: 첫 스레드를 shim 본문(import_module 호출) 안에 붙잡아 두고,
둘째 스레드가 잠금 대기(_bootstrap._lock_unlock_module)에 들어선 것을 본 뒤 놓아 준다.
"""
import importlib
import importlib._bootstrap as _bootstrap
import importlib.util
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (shim 이름, 구현 모듈, 요청 경로에서 쓰는 모양 그대로의 import 문, 받아야 할 속성)
SHIMS = [
    ("analyzer", "packages.medical_shared.compliance_rules.analyzer",
     "from analyzer import ComplianceAnalyzer as got", "ComplianceAnalyzer"),
    ("guideline_loader", "packages.medical_shared.compliance_rules.guideline_loader",
     "from guideline_loader import get_fixed_notices as got", "get_fixed_notices"),
    ("consultation_loader", "packages.medical_shared.compliance_rules.consultation_loader",
     "import consultation_loader\ngot = consultation_loader.load_checklists_by_symptom",
     "load_checklists_by_symptom"),
    ("dbcommon", "packages.medical_shared.dbcommon",
     "from dbcommon import get_conn as got", "get_conn"),
]
_IDS = [s[0] for s in SHIMS]


def _run(stmt, out):
    ns = {}
    try:
        exec(stmt, ns)
        out["got"] = ns["got"]
    except Exception as e:  # 경쟁에서 진 스레드의 ImportError / AttributeError 를 결과로 남긴다
        out["error"] = e


@pytest.mark.parametrize("shim,impl_name,stmt,attr", SHIMS, ids=_IDS)
def test_concurrent_first_import_gets_implementation(monkeypatch, shim, impl_name, stmt, attr):
    impl = importlib.import_module(impl_name)  # 운영에서도 구현은 rag_engine 적재 때 이미 올라와 있다
    monkeypatch.delitem(sys.modules, shim, raising=False)

    in_shim = threading.Event()  # 첫 스레드가 shim 본문 안에 있다
    waiting = threading.Event()  # 둘째 스레드가 sys.modules 에서 shim 을 집고 잠금 대기에 들어섰다

    real_import_module = importlib.import_module

    def held_import_module(name, package=None):
        if name == impl_name and threading.current_thread().name == "first":
            in_shim.set()
            waiting.wait(timeout=5)
        return real_import_module(name, package)

    real_lock_unlock = _bootstrap._lock_unlock_module

    def spy_lock_unlock(name):
        if name == shim and threading.current_thread().name == "second":
            waiting.set()
        return real_lock_unlock(name)

    monkeypatch.setattr(importlib, "import_module", held_import_module)
    monkeypatch.setattr(_bootstrap, "_lock_unlock_module", spy_lock_unlock)

    first, second = {}, {}

    def second_body():
        if in_shim.wait(timeout=5):
            _run(stmt, second)

    t1 = threading.Thread(target=_run, args=(stmt, first), name="first")
    t2 = threading.Thread(target=second_body, name="second")
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert not t1.is_alive() and not t2.is_alive()

    if not waiting.is_set():
        pytest.skip("이 Python 에서는 shim 실행 중 잠금 대기 순서를 만들 수 없다")
    assert "error" not in first, first.get("error")
    assert "error" not in second, f"둘째 스레드 실패: {second.get('error')!r}"
    assert first["got"] is getattr(impl, attr)
    assert second["got"] is getattr(impl, attr)
    assert sys.modules[shim] is impl


@pytest.mark.parametrize("shim,impl_name,stmt,attr", SHIMS, ids=_IDS)
def test_stale_shim_object_delegates_to_implementation(monkeypatch, shim, impl_name, stmt, attr):
    """교체 전 shim 객체를 쥔 쪽도 구현의 이름을 본다 — 테스트가 구현에 건 패치까지."""
    impl = importlib.import_module(impl_name)
    spec = importlib.util.spec_from_file_location(shim, os.path.join(_ROOT, f"{shim}.py"))
    stale = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, shim, stale)
    spec.loader.exec_module(stale)

    assert sys.modules[shim] is impl
    assert stale is not impl
    assert getattr(stale, attr) is getattr(impl, attr)
    sentinel = object()
    monkeypatch.setattr(impl, attr, sentinel)
    assert getattr(stale, attr) is sentinel
    with pytest.raises(AttributeError):
        getattr(stale, "no_such_name_in_impl")


def test_patch_target_is_still_implementation():
    """tests 가 쓰는 patch('analyzer.ComplianceAnalyzer') 는 구현 모듈을 바꾼다(rag_engine 이 보는 것)."""
    from unittest.mock import patch

    impl = importlib.import_module("packages.medical_shared.compliance_rules.analyzer")
    with patch("analyzer.ComplianceAnalyzer") as mocked:
        from analyzer import ComplianceAnalyzer
        assert ComplianceAnalyzer is mocked
        assert impl.ComplianceAnalyzer is mocked
