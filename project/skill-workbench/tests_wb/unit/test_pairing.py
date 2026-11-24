import sys
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.core.pairing import CODE_LENGTH, PAIR_FILE, PairingStore  # noqa: E402
from agent.core.session import SessionStore  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_code_is_single_use_and_file_holds_only_code(tmp_path):
    clock = Clock()
    store = PairingStore(tmp_path, clock=clock)
    result = store.create()
    assert len(result["code"]) == CODE_LENGTH
    pair_file = tmp_path / PAIR_FILE
    assert pair_file.is_file()
    assert pair_file.read_text(encoding="utf-8").strip() == result["code"]
    assert store.consume(result["code"]) is True
    with pytest.raises(DomainError) as error:
        store.consume(result["code"])
    assert error.value.code == "E_PAIR_CODE_USED"


def test_code_expires(tmp_path):
    clock = Clock()
    store = PairingStore(tmp_path, clock=clock)
    code = store.create()["code"]
    clock.now += 121
    with pytest.raises(DomainError) as error:
        store.consume(code)
    assert error.value.code == "E_PAIR_CODE_EXPIRED"


def test_unknown_code(tmp_path):
    store = PairingStore(tmp_path, clock=Clock())
    with pytest.raises(DomainError) as error:
        store.consume("not-a-code")
    assert error.value.code == "E_PAIR_CODE_INVALID"


def test_session_ttl_and_revoke():
    clock = Clock()
    sessions = SessionStore(ttl=8 * 3600, clock=clock)
    issued = sessions.issue()
    assert sessions.validate(issued["token"]) is True
    clock.now += 8 * 3600 + 1
    assert sessions.validate(issued["token"]) is False
    second = sessions.issue()
    sessions.revoke(second["token"])
    assert sessions.validate(second["token"]) is False