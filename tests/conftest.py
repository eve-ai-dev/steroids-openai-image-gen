"""Safe validation default: disposable homes, synthetic secrets, no sockets."""
import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HERMES_HOME', str(home))
    monkeypatch.setenv('HERMES_MANAGED_DIR', str(home))
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://managed.invalid/v1')
    monkeypatch.setenv('HERMES_ALLOW_PRIVATE_URLS', 'false')
    def deny_network(*args, **kwargs):
        raise AssertionError('network forbidden in isolated plugin tests')
    monkeypatch.setattr(socket.socket, 'connect', deny_network)
    monkeypatch.setattr(socket.socket, 'connect_ex', deny_network)
