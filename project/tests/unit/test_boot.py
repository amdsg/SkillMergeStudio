from __future__ import annotations

import threading
from pathlib import Path

from skillmerge import app as app_module
from skillmerge.app import build_app

ROOT = Path(__file__).resolve().parents[2]


def test_wrappers_only_delegate_to_server():
    expected = {
        "start.bat": "python server.py",
        "start.command": "python3 server.py",
        "start.sh": "python3 server.py",
    }
    for name, marker in expected.items():
        path = ROOT / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8", errors="replace")
        assert marker in text, name
        assert "if " not in text.lower(), name
        assert "--port" not in text, name


def test_runtime_files_are_written_and_cleaned(tmp_path):
    data_dir = tmp_path / "data"
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(data_dir), check_pid=False)
    try:
        port_text = (data_dir / "port.txt").read_text(encoding="utf-8")
        assert port_text.startswith("port=")
        assert "url=http://127.0.0.1:" in port_text
        pid_text = (data_dir / "pid.txt").read_text(encoding="utf-8").strip()
        assert pid_text.isdigit()
        assert server.server_address[1] > 0
    finally:
        app_module._cleanup(str(data_dir), server, server.ctx.jobs, server.ctx.db)
    assert not (data_dir / "pid.txt").exists()
    assert not (data_dir / "port.txt").exists()


def test_second_instance_detected_while_first_alive(tmp_path):
    data_dir = tmp_path / "data"
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(data_dir), check_pid=False)
    try:
        assert app_module.existing_instance(str(data_dir))
        second = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(data_dir), check_pid=True)
        assert second is None
    finally:
        app_module._cleanup(str(data_dir), server, server.ctx.jobs, server.ctx.db)