"""Tests pour `chessable_to_pgn.utilities`."""

import pytest

from chess_toolbox.bin.chessable_to_pgn import utilities


class TestIsInteger:
    """Tests pour `is_integer`."""

    @pytest.mark.parametrize("value", ["42", "-7", "0"])
    def test_accepts_valid_integers(self, value: str) -> None:
        """Une chaîne représentant un entier (positif, négatif, nul) est acceptée."""
        assert utilities.is_integer(value) is True

    @pytest.mark.parametrize("value", ["", "abc", "4.2", "12a"])
    def test_rejects_non_integers(self, value: str) -> None:
        """Une chaîne non convertible en entier est rejetée."""
        assert utilities.is_integer(value) is False


class TestGetOptionFromList:
    """Tests pour `getOptionFromList`, qui lit `sys.argv` directement."""

    def test_returns_index_of_matching_option(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """L'option trouvée (insensible à la casse) retourne son index dans la liste."""
        monkeypatch.setattr("sys.argv", ["prog", "ALL"])
        assert utilities.getOptionFromList(1, "web", ["all", "none"]) == 0

    def test_returns_none_when_argument_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Aucun argument à l'index demandé retourne None."""
        monkeypatch.setattr("sys.argv", ["prog"])
        assert utilities.getOptionFromList(1, "web", ["all", "none"]) is None

    def test_returns_none_when_argument_not_in_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un argument présent mais absent de la liste d'options retourne None."""
        monkeypatch.setattr("sys.argv", ["prog", "bogus"])
        assert utilities.getOptionFromList(1, "web", ["all", "none"]) is None


class TestGetOpenOption:
    """Tests pour `getOpenOption`, qui lit `sys.argv` directement."""

    def test_returns_raw_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """La valeur brute de l'argument est retournée telle quelle."""
        monkeypatch.setattr("sys.argv", ["prog", "/some/path"])
        assert utilities.getOpenOption(1, "htmlroot") == "/some/path"

    def test_returns_none_when_argument_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Aucun argument à l'index demandé retourne None."""
        monkeypatch.setattr("sys.argv", ["prog"])
        assert utilities.getOpenOption(1, "htmlroot") is None
