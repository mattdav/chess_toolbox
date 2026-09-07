"""Tests pour `chessable_to_pgn.command_line`."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from chess_toolbox.bin.chessable_to_pgn.command_line import (
    _build_parser,
    _split_integer_tokens,
    getNextItemToProcess,
    processCommandLineParams,
)
from chess_toolbox.bin.chessable_to_pgn.pgn_writer import Pgn, PgnMode
from chess_toolbox.bin.chessable_to_pgn.web_fetch import FetchMode, WebFetch
from chess_toolbox.config.settings import settings


@pytest.fixture(autouse=True)
def _reset_modes() -> Any:
    """Remet les modes globaux `WebFetch`/`Pgn` à leur état par défaut."""
    yield
    WebFetch.doFetch = FetchMode.FETCH_NEW
    Pgn.doPgn = PgnMode.PGN_INCREMENTAL
    Pgn.PGN_WRITE_KEY_MOVE = True


def _set_argv(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr("sys.argv", ["prog", *args])


class TestSplitIntegerTokens:
    """Tests pour `_split_integer_tokens`."""

    def test_separates_valid_and_invalid(self) -> None:
        """Les tokens numériques et non numériques sont séparés."""
        valid, invalid = _split_integer_tokens(["1", "abc", "2"])
        assert valid == ["1", "2"]
        assert invalid == ["abc"]

    def test_empty_input_returns_empty_lists(self) -> None:
        """Une liste vide retourne deux listes vides."""
        assert _split_integer_tokens([]) == ([], [])


class TestBuildParser:
    """Tests pour `_build_parser`."""

    def test_parses_known_flags(self) -> None:
        """Les flags legacy à un tiret sont reconnus."""
        parser = _build_parser()
        args = parser.parse_args(["-courses", "1", "2", "-web", "all"])
        assert args.courses == ["1", "2"]
        assert args.web == "all"


class TestProcessCommandLineParams:
    """Tests pour `processCommandLineParams`."""

    def test_defaults_to_batch_with_no_courses_or_variations(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sans argument, le mode batch est utilisé et les listes sont vides."""
        _set_argv(monkeypatch)
        mode, courses, variations = processCommandLineParams()
        assert mode == "batch"
        assert courses == []
        assert variations == []
        assert WebFetch.doFetch == FetchMode.FETCH_NEW
        assert Pgn.doPgn == PgnMode.PGN_INCREMENTAL

    def test_interactive_flag_sets_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`-interactive` positionne le mode de traitement à `interactive`."""
        _set_argv(monkeypatch, "-interactive")
        mode, _courses, _variations = processCommandLineParams()
        assert mode == "interactive"

    def test_courses_and_variations_split_valid_from_invalid(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Les identifiants non numériques sont signalés, pas rejetés en bloc."""
        _set_argv(monkeypatch, "-courses", "1", "x", "-variations", "2", "y")
        _mode, courses, variations = processCommandLineParams()
        assert courses == ["1"]
        assert variations == ["2"]
        out = capsys.readouterr().out
        assert "<x>" in out
        assert "<y>" in out

    def test_web_all_sets_fetch_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`-web all` positionne `WebFetch.doFetch` sur `FETCH_ALL`."""
        _set_argv(monkeypatch, "-web", "all")
        processCommandLineParams()
        assert WebFetch.doFetch == FetchMode.FETCH_ALL

    def test_web_invalid_value_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Une valeur `-web` invalide retourne un triplet `None`."""
        _set_argv(monkeypatch, "-web", "bogus")
        result = processCommandLineParams()
        assert result == (None, None, None)

    def test_key_flag_enables_key_move(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`-key` active `Pgn.PGN_WRITE_KEY_MOVE`."""
        _set_argv(monkeypatch, "-nokey")
        processCommandLineParams()
        assert Pgn.PGN_WRITE_KEY_MOVE is False

    def test_nokey_flag_disables_key_move(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`-nokey` désactive `Pgn.PGN_WRITE_KEY_MOVE`."""
        _set_argv(monkeypatch, "-key")
        processCommandLineParams()
        assert Pgn.PGN_WRITE_KEY_MOVE is True

    def test_pgn_after_sets_pgn_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`-pgn after` positionne `Pgn.doPgn` sur `PGN_AFTER`."""
        _set_argv(monkeypatch, "-pgn", "after")
        processCommandLineParams()
        assert Pgn.doPgn == PgnMode.PGN_AFTER

    def test_pgn_invalid_value_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Une valeur `-pgn` invalide retourne un triplet `None`."""
        _set_argv(monkeypatch, "-pgn", "bogus")
        result = processCommandLineParams()
        assert result == (None, None, None)

    def test_environment_flags_update_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Les flags d'environnement mettent à jour `settings` en place."""
        _set_argv(
            monkeypatch,
            "-pgnroot",
            "/pgn",
            "-htmlroot",
            "/html",
            "-browserbinary",
            "/bin/firefox",
            "-browserprofiledir",
            "/profile",
        )
        processCommandLineParams()
        assert settings.chessable_pgn_cache == Path("/pgn")
        assert settings.chessable_html_cache == Path("/html")
        assert settings.firefox_binary_path == "/bin/firefox"
        assert settings.firefox_automation_profile_dir == "/profile"

    def test_unknown_argument_is_reported_but_not_fatal(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Un argument inconnu affiche un avertissement sans faire échouer l'appel."""
        _set_argv(monkeypatch, "-bogusflag")
        mode, _courses, _variations = processCommandLineParams()
        assert mode == "batch"
        assert "bogusflag" in capsys.readouterr().out

    def test_missing_value_for_web_flag_aborts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`-web` sans valeur suivante retourne un triplet `None` (pas de crash)."""
        _set_argv(monkeypatch, "-web")
        result = processCommandLineParams()
        assert result == (None, None, None)


def _make_input(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    """Remplace `input` par un double consommant `responses` dans l'ordre."""
    it: Iterator[str] = iter(responses)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


class TestGetNextItemToProcess:
    """Tests pour `getNextItemToProcess`."""

    def test_quit_immediately(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Saisir 'q' en premier retourne `(True, None, None)`."""
        _make_input(monkeypatch, ["q"])
        assert getNextItemToProcess() == (True, None, None)

    def test_course_then_default_modes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Un cours saisi avec les modes par défaut (1, 2) est retourné."""
        _make_input(monkeypatch, ["c", "123", "1", "2"])
        quit_, courses, variations = getNextItemToProcess()
        assert quit_ is False
        assert courses == ["123"]
        assert variations == []
        assert WebFetch.doFetch == FetchMode.FETCH_NEW
        assert Pgn.doPgn == PgnMode.PGN_INCREMENTAL

    def test_variation_then_modes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Une variation saisie est retournée dans `vOut`."""
        _make_input(monkeypatch, ["v", "456", "1", "2"])
        quit_, courses, variations = getNextItemToProcess()
        assert quit_ is False
        assert courses == []
        assert variations == ["456"]

    def test_blank_source_defaults_to_course(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Une saisie vide est traitée comme un choix de cours."""
        _make_input(monkeypatch, ["", "789", "1", "2"])
        quit_, courses, _variations = getNextItemToProcess()
        assert quit_ is False
        assert courses == ["789"]

    def test_quit_during_web_mode_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Un 'q' pendant le choix du mode web retourne `(True, None, None)`."""
        _make_input(monkeypatch, ["c", "123", "q"])
        assert getNextItemToProcess() == (True, None, None)

    def test_quit_during_pgn_mode_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Un 'q' pendant le choix du mode pgn retourne `(True, None, None)`."""
        _make_input(monkeypatch, ["c", "123", "1", "q"])
        assert getNextItemToProcess() == (True, None, None)

    def test_non_default_modes_are_applied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Des choix de mode non-défaut positionnent bien `doFetch`/`doPgn`."""
        _make_input(monkeypatch, ["c", "123", "2", "3"])
        getNextItemToProcess()
        assert WebFetch.doFetch == FetchMode.FETCH_ALL
        assert Pgn.doPgn == PgnMode.PGN_AFTER
