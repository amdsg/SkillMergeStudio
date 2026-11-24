from __future__ import annotations

import socket

import pytest

from skillmerge.http.server import create_server


def _free_high_port() -> int:
    for port in range(9100, 9200):
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            continue
        finally:
            probe.close()
        return port
    pytest.skip("9100-9199 端口均被占用")


def test_preferred_port_above_end_port_is_attempted():
    port = _free_high_port()
    server, actual = create_server(
        "127.0.0.1",
        None,
        None,
        "",
        None,
        None,
        None,
        preferred_port=port,
        end_port=8865,
    )
    try:
        assert actual == port
        assert server.port == port
    finally:
        server.server_close()