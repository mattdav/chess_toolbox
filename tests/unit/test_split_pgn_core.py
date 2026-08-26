"""Tests pour `chess_toolbox.bin.split_pgn.core`."""

import io
from pathlib import Path

import chess.pgn
import pytest

from chess_toolbox.bin.split_pgn.core import (
    copy_subtree,
    extract_branches,
    follow_moves,
    list_variations,
    main,
    node_to_pgn_string,
    parse_pgn_file,
    safe_filename,
    san_to_uci_sequence,
)

_PGN_WITH_SIDELINE = """[Event "Test"]
[White "W"]
[Black "B"]
[Result "*"]

1. e4 c5 (1... e5 2. Nf3) 2. Nf3 *
"""

_PGN_NO_BRANCH = """[Event "Test"]
[White "W"]
[Black "B"]
[Result "*"]

1. e4 e5 *
"""


def _game() -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(_PGN_WITH_SIDELINE))
    assert game is not None
    return game


class TestParsePgnFile:
    """Tests pour `parse_pgn_file`."""

    def test_reads_a_valid_pgn_file(self, tmp_path: Path) -> None:
        """Un fichier PGN valide retourne l'objet `Game` correspondant."""
        pgn_file = tmp_path / "repertoire.pgn"
        pgn_file.write_text(_PGN_WITH_SIDELINE, encoding="utf-8")
        game = parse_pgn_file(str(pgn_file))
        assert game.headers["White"] == "W"

    def test_raises_on_unparsable_file(self, tmp_path: Path) -> None:
        """Un fichier vide (aucun jeu lisible) lève `ValueError`."""
        pgn_file = tmp_path / "empty.pgn"
        pgn_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="Impossible de lire"):
            parse_pgn_file(str(pgn_file))


class TestSanToUciSequence:
    """Tests pour `san_to_uci_sequence`."""

    def test_converts_numbered_san_tokens(self) -> None:
        """Une séquence SAN numérotée est convertie en coups UCI."""
        assert san_to_uci_sequence("1.e4 c5") == ["e2e4", "c7c5"]

    def test_accepts_raw_uci_tokens(self) -> None:
        """Des tokens déjà en UCI et légaux sont acceptés tels quels."""
        assert san_to_uci_sequence("e2e4 c7c5") == ["e2e4", "c7c5"]

    def test_raises_on_illegal_move(self) -> None:
        """Un coup illégal lève `ValueError` avec un message explicite."""
        with pytest.raises(ValueError, match="Coup illisible"):
            san_to_uci_sequence("1.e4 e4")


class TestFollowMoves:
    """Tests pour `follow_moves`."""

    def test_follows_mainline(self) -> None:
        """La ligne principale est suivie jusqu'au nœud demandé."""
        node, board = follow_moves(_game(), ["e2e4", "c7c5"])
        assert node is not None
        assert node.move == chess.Move.from_uci("c7c5")

    def test_follows_sideline_variation(self) -> None:
        """Une sous-variante entre parenthèses est également suivie."""
        node, _board = follow_moves(_game(), ["e2e4", "e7e5"])
        assert node is not None
        assert node.move == chess.Move.from_uci("e7e5")

    def test_returns_none_when_sequence_absent(self) -> None:
        """Une séquence absente de l'arbre retourne `(None, board_partiel)`."""
        node, board = follow_moves(_game(), ["e2e4", "d7d5"])
        assert node is None
        expected_board = chess.Board()
        expected_board.push(chess.Move.from_uci("e2e4"))
        assert board.fen() == expected_board.fen()


class TestCopySubtreeAndNodeToPgnString:
    """Tests pour `copy_subtree` (via `node_to_pgn_string`)."""

    def test_generates_pgn_with_headers_and_subvariations(self) -> None:
        """Le PGN généré porte le label et conserve les sous-variantes."""
        game = _game()
        start_node, start_board = follow_moves(game, ["e2e4"])
        assert start_node is not None
        pgn_text = node_to_pgn_string(
            start_node, start_board, dict(game.headers), "1.e4"
        )
        assert '[White "1.e4"]' in pgn_text
        assert "c5" in pgn_text
        assert "e5" in pgn_text

    def test_copy_subtree_skips_illegal_moves(self) -> None:
        """Une variation dont le coup est illégal sur le board fourni est ignorée."""

        class _FakeVar:
            def __init__(self, move: chess.Move) -> None:
                self.move = move

        class _FakeSrcNode:
            def __init__(self, variations: list[_FakeVar]) -> None:
                self.variations = variations

        illegal_move = chess.Move.from_uci("e2e5")
        src = _FakeSrcNode([_FakeVar(illegal_move)])
        dst = chess.pgn.Game()
        copy_subtree(src, dst, chess.Board())
        assert dst.variations == []


class TestListVariations:
    """Tests pour `list_variations`."""

    def test_lists_direct_children_at_depth_one(self) -> None:
        """À profondeur 1, chaque variation directe produit un label."""
        game = _game()
        start_node, start_board = follow_moves(game, ["e2e4"])
        assert start_node is not None
        results = list_variations(start_node, start_board, depth=1)
        assert len(results) == 2
        assert any("c5" in r for r in results)
        assert any("e5" in r for r in results)


class TestSafeFilename:
    """Tests pour `safe_filename`."""

    def test_replaces_spaces_with_underscore(self) -> None:
        """Les espaces sont remplacés par des underscores."""
        assert safe_filename("a b") == "a_b"

    def test_strips_non_word_characters(self) -> None:
        """Les caractères hors `\\w`/`-` sont supprimés."""
        assert safe_filename("1...c5") == "1c5"

    def test_falls_back_to_variante_when_empty(self) -> None:
        """Un label qui ne produit aucun caractère valide retombe sur 'variante'."""
        assert safe_filename("!!!") == "variante"


class TestExtractBranches:
    """Tests pour `extract_branches`."""

    def test_writes_one_file_per_branch(self, tmp_path: Path) -> None:
        """Un fichier PGN est créé par branche au niveau de profondeur demandé."""
        game = _game()
        start_node, start_board = follow_moves(game, ["e2e4"])
        assert start_node is not None
        count = extract_branches(
            start_node, start_board, dict(game.headers), str(tmp_path), depth=1
        )
        assert count == 2
        assert len(list(tmp_path.glob("*.pgn"))) == 2


class TestMain:
    """Tests d'intégration pour `main`."""

    def _write_pgn(
        self, tmp_path: Path, content: str, name: str = "repertoire.pgn"
    ) -> Path:
        pgn_file = tmp_path / name
        pgn_file.write_text(content, encoding="utf-8")
        return pgn_file

    def test_list_mode_prints_variations_without_writing_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`--list` affiche les variantes sans créer de fichier."""
        pgn_file = self._write_pgn(tmp_path, _PGN_WITH_SIDELINE)
        main([str(pgn_file), "--moves", "1.e4", "--list"])
        out = capsys.readouterr().out
        assert "c5" in out
        assert "e5" in out
        created = [p for p in tmp_path.glob("*.pgn") if p != pgn_file]
        assert created == []

    def test_extract_mode_writes_files_to_explicit_output(self, tmp_path: Path) -> None:
        """Sans `--list`, les fichiers sont écrits dans `--output`."""
        pgn_file = self._write_pgn(tmp_path, _PGN_WITH_SIDELINE)
        out_dir = tmp_path / "out"
        main([str(pgn_file), "--moves", "1.e4", "--output", str(out_dir)])
        assert len(list(out_dir.glob("*.pgn"))) == 2

    def test_default_output_dir_uses_pgn_basename(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sans `--output`, le dossier par défaut est `<nom_pgn>_split`."""
        self._write_pgn(tmp_path, _PGN_WITH_SIDELINE)
        monkeypatch.chdir(tmp_path)
        main(["repertoire.pgn", "--moves", "1.e4"])
        assert len(list((tmp_path / "repertoire_split").glob("*.pgn"))) == 2

    def test_no_moves_uses_initial_position(self, tmp_path: Path) -> None:
        """Sans `--moves`, la découpe part de la position initiale."""
        pgn_file = self._write_pgn(tmp_path, _PGN_WITH_SIDELINE)
        out_dir = tmp_path / "out"
        main([str(pgn_file), "--output", str(out_dir)])
        assert len(list(out_dir.glob("*.pgn"))) == 1

    def test_illegal_move_sequence_exits_with_code_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Une séquence de coups illisible arrête le programme (code 1)."""
        pgn_file = self._write_pgn(tmp_path, _PGN_WITH_SIDELINE)
        with pytest.raises(SystemExit) as exc_info:
            main([str(pgn_file), "--moves", "1.e4 e4"])
        assert exc_info.value.code == 1
        assert "Coup illisible" in capsys.readouterr().out

    def test_absent_move_sequence_exits_with_code_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Une séquence absente de l'arbre arrête le programme (code 1)."""
        pgn_file = self._write_pgn(tmp_path, _PGN_WITH_SIDELINE)
        with pytest.raises(SystemExit) as exc_info:
            main([str(pgn_file), "--moves", "1.d4"])
        assert exc_info.value.code == 1
        assert "introuvable" in capsys.readouterr().out

    def test_no_variations_at_start_exits_with_code_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Une position sans variante disponible arrête le programme (code 0)."""
        pgn_file = self._write_pgn(tmp_path, _PGN_NO_BRANCH, name="lineaire.pgn")
        with pytest.raises(SystemExit) as exc_info:
            main([str(pgn_file), "--moves", "1.e4 e5"])
        assert exc_info.value.code == 0
        assert "Aucune variante" in capsys.readouterr().out
