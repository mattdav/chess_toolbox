"""Tests pour `chess_toolbox.__main__`."""

from pathlib import Path
from typing import Any

import pytest

import chess_toolbox.__main__ as main_module
import chess_toolbox.bin.chessable_to_pgn as chessable_to_pgn
import chess_toolbox.bin.split_pgn as split_pgn
from chess_toolbox.bin.chessable_to_pgn import web_fetch


@pytest.fixture(autouse=True)
def _noop_load_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empêche `_load_env` de lire un vrai `.env` pendant les tests."""
    monkeypatch.setattr(main_module, "load_dotenv", lambda _path: None)


def _set_argv(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr("sys.argv", ["chess_toolbox", *args])


class TestLoadEnv:
    """Tests pour `_load_env`."""

    def test_loads_dotenv_from_cwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Le `.env` chargé est celui du répertoire de travail courant."""
        calls: list[Path] = []
        monkeypatch.setattr(main_module, "load_dotenv", lambda path: calls.append(path))
        main_module._load_env()
        assert calls == [Path.cwd() / ".env"]


class TestMainExtractChessable:
    """Tests pour `main()` sur la sous-commande `extract-chessable`."""

    class _FakeFetcher:
        def __enter__(self) -> "TestMainExtractChessable._FakeFetcher":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

    def test_runs_chessable_main_within_fetcher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Les arguments engine sont transmis tels quels au moteur chessable-to-pgn."""
        _set_argv(monkeypatch, "extract-chessable", "-courses", "1")
        calls: list[list[str]] = []
        monkeypatch.setattr(
            chessable_to_pgn,
            "main",
            lambda: calls.append(list(__import__("sys").argv)),
        )
        monkeypatch.setattr(web_fetch, "ChessableFetcher", self._FakeFetcher)
        main_module.main()
        assert calls == [["chess_toolbox", "-courses", "1"]]

    def test_relogin_flag_triggers_login_and_is_stripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--relogin` déclenche la reconnexion et n'est pas transmis au moteur."""
        _set_argv(monkeypatch, "extract-chessable", "--relogin", "-courses", "1")
        login_calls: list[None] = []
        monkeypatch.setattr(
            web_fetch, "login_and_save_cookies", lambda: login_calls.append(None)
        )
        engine_argv: list[list[str]] = []
        monkeypatch.setattr(
            chessable_to_pgn,
            "main",
            lambda: engine_argv.append(list(__import__("sys").argv)),
        )
        monkeypatch.setattr(web_fetch, "ChessableFetcher", self._FakeFetcher)
        main_module.main()
        assert login_calls == [None]
        assert engine_argv == [["chess_toolbox", "-courses", "1"]]

    def test_auth_error_exits_with_code_2(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Une `ChessableAuthError` provoque un `sys.exit(2)` avec message affiché."""
        _set_argv(monkeypatch, "extract-chessable")

        def _raise() -> None:
            raise web_fetch.ChessableAuthError("session expirée")

        monkeypatch.setattr(chessable_to_pgn, "main", _raise)
        monkeypatch.setattr(web_fetch, "ChessableFetcher", self._FakeFetcher)
        with pytest.raises(SystemExit) as exc_info:
            main_module.main()
        assert exc_info.value.code == 2
        assert "session expirée" in capsys.readouterr().out


class TestMainStartBrowserAndLogin:
    """Tests pour les sous-commandes `chessable-start-browser`/`chessable-login`."""

    def test_start_browser_delegates_to_web_fetch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`chessable-start-browser` appelle `start_automation_browser`."""
        _set_argv(monkeypatch, "chessable-start-browser")
        calls: list[None] = []
        monkeypatch.setattr(
            web_fetch, "start_automation_browser", lambda: calls.append(None)
        )
        main_module.main()
        assert calls == [None]

    def test_login_uses_default_profile_when_omitted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`chessable-login` sans profil utilise le profil `Default`."""
        _set_argv(monkeypatch, "chessable-login")
        calls: list[str] = []
        monkeypatch.setattr(
            web_fetch, "login_and_save_cookies", lambda profile: calls.append(profile)
        )
        main_module.main()
        assert calls == ["Default"]

    def test_login_uses_explicit_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`chessable-login` avec un profil explicite le transmet tel quel."""
        _set_argv(monkeypatch, "chessable-login", "MonProfil")
        calls: list[str] = []
        monkeypatch.setattr(
            web_fetch, "login_and_save_cookies", lambda profile: calls.append(profile)
        )
        main_module.main()
        assert calls == ["MonProfil"]


class TestMainSplitPgn:
    """Tests pour la sous-commande `split-pgn`."""

    def test_builds_argv_with_only_provided_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Seules les options fournies sont transmises à `split_pgn.main`."""
        _set_argv(monkeypatch, "split-pgn", "repertoire.pgn")
        calls: list[list[str]] = []
        monkeypatch.setattr(split_pgn, "main", lambda argv: calls.append(argv))
        main_module.main()
        assert calls == [["repertoire.pgn"]]

    def test_builds_argv_with_all_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Toutes les options fournies sont reconstruites dans l'argv transmis."""
        _set_argv(
            monkeypatch,
            "split-pgn",
            "repertoire.pgn",
            "--moves",
            "1.e4",
            "--depth",
            "2",
            "--output",
            "out/",
            "--list",
        )
        calls: list[list[str]] = []
        monkeypatch.setattr(split_pgn, "main", lambda argv: calls.append(argv))
        main_module.main()
        assert calls == [
            [
                "repertoire.pgn",
                "--moves",
                "1.e4",
                "--depth",
                "2",
                "--output",
                "out/",
                "--list",
            ]
        ]


class TestMainNoCommand:
    """Tests pour l'absence de sous-commande."""

    def test_missing_command_exits_via_argparse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sans sous-commande, argparse échoue (`required=True`) et quitte."""
        _set_argv(monkeypatch)
        with pytest.raises(SystemExit):
            main_module.main()
