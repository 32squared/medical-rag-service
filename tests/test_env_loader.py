"""
env_loader 테스트 — .env 주입(시크릿 없는 임시 파일).
"""

import os

from env_loader import load_env


def test_injects_values(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("FOO_TEST_VAR=hello\n# comment\nBAR_TEST='quoted'\n", encoding="utf-8")
    monkeypatch.delenv("FOO_TEST_VAR", raising=False)
    monkeypatch.delenv("BAR_TEST", raising=False)
    n = load_env(str(p))
    assert n == 2
    assert os.environ["FOO_TEST_VAR"] == "hello"
    assert os.environ["BAR_TEST"] == "quoted"  # 따옴표 제거


def test_does_not_override_existing(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("FOO_TEST_VAR=fromfile\n", encoding="utf-8")
    monkeypatch.setenv("FOO_TEST_VAR", "preset")
    load_env(str(p))
    assert os.environ["FOO_TEST_VAR"] == "preset"  # 환경 우선


def test_override_flag(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("FOO_TEST_VAR=fromfile\n", encoding="utf-8")
    monkeypatch.setenv("FOO_TEST_VAR", "preset")
    load_env(str(p), override=True)
    assert os.environ["FOO_TEST_VAR"] == "fromfile"


def test_missing_file_returns_zero():
    assert load_env(str("/no/such/path/.env")) == 0


def test_ignores_blank_and_comment_lines(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("\n# only comment\n   \nKEY_TEST=v\n", encoding="utf-8")
    monkeypatch.delenv("KEY_TEST", raising=False)
    assert load_env(str(p)) == 1
