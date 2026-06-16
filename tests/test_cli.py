from __future__ import annotations

import builtins

from app import cli


def test_main_without_command_starts_interactive_shell(monkeypatch, capsys) -> None:
    def raise_eof(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    monkeypatch.setattr(cli, "load_runtime_config", lambda args: {"access_token": "token", "user": {"email": "dev@example.com"}})

    assert cli.main([]) == 0

    captured = capsys.readouterr()
    assert "YenkasaCodeAgent interactive mode" in captured.out
    assert "Logged in as dev@example.com" in captured.out


def test_interactive_shell_sends_normal_text_as_query(monkeypatch, capsys) -> None:
    lines = iter(["what repositories are indexed?", "exit"])
    queries = []

    class FakeClient:
        def __init__(self, config: dict) -> None:
            self.config = config

        def query(self, query: str, agent: str | None = None, context: dict | None = None):
            queries.append((query, agent, context))
            return {"agent": "system", "success": True, "result": {"answer": "ok"}}, 12.0, 200

    monkeypatch.setattr(builtins, "input", lambda prompt: next(lines))
    monkeypatch.setattr(cli, "load_runtime_config", lambda args: {"access_token": "token", "user": {}})
    monkeypatch.setattr(cli, "YCAClient", FakeClient)

    assert cli.main([]) == 0

    captured = capsys.readouterr()
    assert queries == [("what repositories are indexed?", None, None)]
    assert "system OK 12ms" in captured.out


def test_login_eof_is_reported_cleanly(monkeypatch, capsys) -> None:
    def raise_eof(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    monkeypatch.setattr(cli, "log_event", lambda event: None)

    assert cli.main(["login"]) == 1

    captured = capsys.readouterr()
    assert "login cancelled" in captured.err
