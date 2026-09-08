"""Tests pour `chessable_to_pgn.pgn_writer`."""

from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup, Tag

from chess_toolbox.bin.chessable_to_pgn import pgn_writer
from chess_toolbox.bin.chessable_to_pgn.pgn_writer import (
    Pgn,
    escapeLastNumberInComments,
    findLastMove,
    findLastRootComment,
    findLastRootVariation,
    insertNullMoveBeforeLastComment,
)
from chess_toolbox.config.settings import settings

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(autouse=True)
def _reset_module_globals() -> None:
    """Réinitialise l'état mutable au niveau module avant chaque test."""
    pgn_writer.count = 0
    pgn_writer.firstMove = True
    pgn_writer.firstMoveNbr = -1
    pgn_writer.lastSeenFenParts = []
    pgn_writer.lastSeenSan = ""
    pgn_writer.keyWritten = False


def _moves(html: str) -> list[Any]:
    """Parse `html` et retourne les enfants directs (Tag) de son élément racine."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(id="root")
    assert isinstance(root, Tag)
    return root.find_all(recursive=False)


class TestIsTerminator:
    """Tests pour `Pgn.isTerminator`."""

    @pytest.mark.parametrize("value", ["*", "1-0", "0-1", "1/2-1/2", " 1-0 "])
    def test_accepts_known_terminators(self, value: str) -> None:
        """Les quatre terminateurs PGN reconnus, espaces superflus inclus, sont OK."""
        assert Pgn.isTerminator(value) is True

    @pytest.mark.parametrize("value", [None, "", "e4", "1-0-1"])
    def test_rejects_non_terminators(self, value: str | None) -> None:
        """None, chaîne vide ou texte quelconque ne sont pas des terminateurs."""
        assert Pgn.isTerminator(value) is False


class TestGetNag:
    """Tests pour `Pgn.getNag`."""

    @pytest.mark.parametrize(
        ("symbol", "nag"),
        [
            ("!", " $1"),
            ("?", " $2"),
            ("!!", " $3"),
            ("??", " $4"),
            ("!?", " $5"),
            ("?!", " $6"),
            ("=", " $11"),
            ("+-", " $18"),
        ],
    )
    def test_maps_trailing_symbol_to_nag(self, symbol: str, nag: str) -> None:
        """Le symbole en suffixe du texte est traduit vers le bon code NAG."""
        assert Pgn.getNag("Nf3" + symbol) == nag

    def test_prefers_two_character_symbol_over_one(self) -> None:
        """`!?` (2 caractères) prime sur `?` (son dernier caractère seul)."""
        assert Pgn.getNag("e4!?") == " $5"

    def test_returns_empty_string_when_no_symbol_recognized(self) -> None:
        """Un texte sans symbole d'annotation reconnu retourne une chaîne vide."""
        assert Pgn.getNag("e4") == ""


class TestBuildGameResult:
    """Tests pour `Pgn.buildGameResult`."""

    def test_wraps_result_with_newlines(self) -> None:
        """Le résultat est entouré de sauts de ligne pour la concaténation PGN."""
        assert Pgn.buildGameResult("1-0") == "\n 1-0 \n\n"


class TestGetGameResult:
    """Tests pour `Pgn.getGameResult`."""

    def test_returns_first_terminator_found(self) -> None:
        """Le premier élément dont le texte est un terminateur est retourné."""
        soup = BeautifulSoup("<div>autre</div><div>1-0</div>", "html.parser")
        tags = soup.find_all("div")
        assert Pgn.getGameResult(tags) == "1-0"

    def test_returns_star_when_no_terminator_present(self) -> None:
        """Si aucun élément n'est un terminateur, `*` est retourné par défaut."""
        soup = BeautifulSoup("<div>autre</div>", "html.parser")
        tags = soup.find_all("div")
        assert Pgn.getGameResult(tags) == "*"


class TestUpdateFEN:
    """Tests pour `Pgn.updateFEN`."""

    def test_replaces_sixth_field_with_first_move_number(self) -> None:
        """Le compteur de coups (6e champ) est remplacé par `firstMoveNbr`."""
        pgn_writer.firstMoveNbr = 7
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        assert (
            Pgn.updateFEN(fen)
            == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 7"
        )


class TestBuildHeader:
    """Tests pour `Pgn.buildHeader`."""

    def _chapter(self) -> list[Any]:
        soup = BeautifulSoup(
            "<ul><li>My Course</li><li>unused</li><li>Chapter One</li></ul>",
            "html.parser",
        )
        return soup.find_all("li")

    def test_builds_header_without_fen_at_starting_position(self) -> None:
        """Aucune balise [FEN] n'est ajoutée si la position de départ est standard."""
        header = Pgn.buildHeader(
            "118788",
            "12345",
            "My Variation, Test",
            self._chapter(),
            "1-0",
            "2.4",
            pgn_writer.STARTING_POSITION,
        )
        assert '[Event "My Course"]' in header
        assert '[White "Chapter One"]' in header
        assert '[Black "My Variation- Test"]' in header
        assert '[Round "2.4"]' in header
        assert '[Result "1-0"]' in header
        assert '[Site "' + settings.base_chessable_url + 'variation/12345/"]' in header
        assert "[FEN" not in header

    def test_builds_header_with_fen_when_not_starting_position(self) -> None:
        """La balise [FEN] est ajoutée si la position de départ n'est pas standard."""
        fen = "r2qr1k1/1b1n1ppp/p1p1p3/1p6/3P4/2P2N2/PPQB1PPP/R3R1K1 w - - 0 1"
        header = Pgn.buildHeader(
            "118788", "12345", "Variation", self._chapter(), "*", "1.1", fen
        )
        assert f'[FEN "{fen}"]' in header


class TestBuildMoveBody:
    """Tests pour `Pgn.buildMoveBody`, construit à partir de la structure DOM réelle."""

    def test_white_then_black_move(self) -> None:
        """Un coup blanc (div) suivi d'un coup noir (span) produit '1. e4 e5 '."""
        moves = _moves(
            '<div id="root">'
            '<div class="whiteMove" data-move="1." data-san="e4" '
            'data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1">'
            "e4</div>"
            '<span class="commentMoveSmall" data-san="e5" data-mid="1" '
            'data-fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2">'
            "e5</span>"
            "</div>"
        )
        assert Pgn.buildMoveBody(moves, 0) == "1. e4 e5 "

    def test_key_move_marker_written_only_once(self) -> None:
        """Le marqueur `-KEY-` n'est inséré qu'au premier coup marqué `is_key`."""
        moves = _moves(
            '<div id="root">'
            '<div class="whiteMove is_key" data-move="1." data-san="e4" '
            'data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1">'
            "e4</div>"
            '<div class="whiteMove is_key" data-move="2." data-san="Nf3" '
            'data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2">'
            "Nf3</div>"
            "</div>"
        )
        assert Pgn.buildMoveBody(moves, 0) == "1.  { -KEY- } e4 2. Nf3 "

    def test_key_move_marker_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Aucun marqueur n'est écrit quand `PGN_WRITE_KEY_MOVE` est désactivé."""
        monkeypatch.setattr(pgn_writer, "PGN_WRITE_KEY_MOVE", False)
        moves = _moves(
            '<div id="root">'
            '<div class="whiteMove is_key" data-move="1." data-san="e4" '
            'data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1">'
            "e4</div></div>"
        )
        assert Pgn.buildMoveBody(moves, 0) == "1. e4 "

    def test_comment_in_variation(self) -> None:
        """Un `span.commentInVariation` est enveloppé en `{ ... }`."""
        moves = _moves(
            '<div id="root"><span class="commentInVariation">Nice idea</span></div>'
        )
        assert Pgn.buildMoveBody(moves, 0) == " { Nice idea } "

    def test_game_terminator_in_opening_num(self) -> None:
        """Un `div.openingNum` avec terminateur est entouré de sauts de ligne."""
        moves = _moves('<div id="root"><div class="openingNum">1-0</div></div>')
        assert Pgn.buildMoveBody(moves, 0) == "\n\n 1-0\n\n"

    def test_nag_annotation_nested_in_move(self) -> None:
        """Une annotation imbriquée dans le coup (DOM réel) ajoute son NAG."""
        moves = _moves(
            '<div id="root">'
            '<div class="whiteMove" data-move="1." data-san="e4" '
            'data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1">'
            'e4<span class="annotation" data-original-title="Good move">!</span>'
            "</div></div>"
        )
        assert Pgn.buildMoveBody(moves, 0) == "1. e4  $1 "

    def test_nested_variation_wrapped_in_parentheses(self) -> None:
        """Un `span.commentTopvar` enveloppe récursivement entre parenthèses."""
        moves = _moves(
            '<div id="root"><span class="commentTopvar">'
            '<div class="whiteMove" data-move="3." data-san="Nf3" '
            'data-fen="rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 0 3">'
            "Nf3</div></span></div>"
        )
        assert Pgn.buildMoveBody(moves, 0) == " ( 3. Nf3  ) \n"


class TestCreatePgnFromHtml:
    """Test d'intégration de `Pgn.createPgnFromHtml` sur une page synthétique."""

    def test_generates_full_pgn_from_synthetic_variation_page(self) -> None:
        """L'assemblage en-tête + coups + résultat produit un PGN cohérent.

        Le terminateur (`div.openingNum`) doit être un enfant direct de
        `#theOpeningMoves` : `WebFetch.getVariationParts` l'extrait via
        `findChildren("div", recursive=False)`, distinct des coups (`findChildren
        ("span", recursive=False)`) qui vivent dans le `<span>` englobant, comme
        observé sur une page de variation réelle.
        """
        variation_html = (
            '<div id="theOpeningTitle">My Variation</div>'
            '<div class="allOpeningDetails">'
            "<ul><li>My Course</li><li>unused</li><li>Chapter One</li></ul>"
            "</div>"
            '<div id="theOpeningMoves"><span>'
            '<div class="whiteMove" data-move="1." data-san="e4" '
            'data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1">'
            "e4</div>"
            '<span class="commentMoveSmall" data-san="e5" data-mid="1" '
            'data-fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2">'
            "e5</span>"
            "</span>"
            '<div class="openingNum">1-0</div>'
            "</div>"
            '<input id="inputFEN" value="' + pgn_writer.STARTING_POSITION + '"/>'
        )
        variation = BeautifulSoup(variation_html, "html.parser")

        result = Pgn.createPgnFromHtml("118788", "12345", variation, "1.1")

        assert result is not None
        assert '[White "Chapter One"]' in result
        assert '[Black "My Variation"]' in result
        assert '[Result "1-0"]' in result
        assert "1. e4 e5" in result
        assert result.strip().endswith("1-0")

    def test_returns_none_when_chapter_is_empty(self) -> None:
        """Sans `div.allOpeningDetails` exploitable, `chapter` vide donne None."""
        variation = BeautifulSoup("<div>page inattendue</div>", "html.parser")
        assert Pgn.createPgnFromHtml("118788", "12345", variation, "1.1") is None


class TestFindLastRootComment:
    """Tests pour `findLastRootComment`."""

    def test_finds_last_comment_at_root_depth(self) -> None:
        """Le dernier `{` situé à la profondeur racine (hors variation) est retourné."""
        pgn = "1. e4 { a } ( 1. Nf3 { nested } ) { last }"
        index, opens, closes = findLastRootComment(pgn)
        assert pgn[index:].startswith("{ last }")
        assert len(opens) == 3
        assert len(closes) == 3

    def test_returns_minus_one_when_no_comment(self) -> None:
        """Sans accolade dans le texte, l'index retourné est -1."""
        index, opens, closes = findLastRootComment("1. e4 e5 *")
        assert index == -1
        assert opens == []
        assert closes == []


class TestFindLastRootVariation:
    """Tests pour `findLastRootVariation`."""

    def test_finds_last_variation_at_root_depth(self) -> None:
        """La dernière parenthèse ouvrante au niveau racine est retournée."""
        pgn = "1. e4 ( 1. d4 ( 1. c4 ) ) ( 1. Nf3 )"
        index = findLastRootVariation(pgn)
        assert pgn[index:].startswith("( 1. Nf3 )")

    def test_returns_minus_one_when_no_variation(self) -> None:
        """Sans parenthèse dans le texte, l'index retourné est -1."""
        assert findLastRootVariation("1. e4 e5 *") == -1


class TestFindLastMove:
    """Tests pour `findLastMove`."""

    def test_identifies_last_move_variation_and_comment_tokens(self) -> None:
        """Les index (en tokens) du dernier coup/variation/commentaire sont corrects."""
        pgn = "1. e4 ( 1. Nf3 ) { Trailing Comment }"
        last_move, last_variation, last_comment = findLastMove(pgn)
        tokens = pgn.split()
        assert tokens[last_move] == "e4"
        assert tokens[last_variation] == "("
        assert tokens[last_comment] == "{"

    def test_ignores_move_numbers_nags_and_null_move(self) -> None:
        """Numéros de coup, NAG et coup nul ne sont jamais un 'dernier coup'."""
        pgn = "1. e4 $1 Z0"
        last_move, _last_variation, _last_comment = findLastMove(pgn)
        assert pgn.split()[last_move] == "e4"

    def test_ignores_tokens_inside_header_tags(self) -> None:
        """Le contenu entre crochets (en-têtes PGN) n'est jamais pris pour un coup."""
        pgn = '[Event "Some Event"] 1. e4'
        last_move, _last_variation, _last_comment = findLastMove(pgn)
        tokens = pgn.split()
        assert tokens[last_move] == "e4"


class TestInsertNullMoveBeforeLastComment:
    """Tests pour `insertNullMoveBeforeLastComment`."""

    def test_inserts_null_move_when_ending_is_move_variation_comment(self) -> None:
        """Une séquence coup-variation-commentaire reçoit un `Z0` avant le commentaire.

        Le terminateur (`*`) n'est pas encore présent à ce stade du pipeline réel :
        `insertNullMoveBeforeLastComment` s'exécute avant que `buildGameResult` ne
        l'ajoute (voir `Pgn.createPgnFromHtml`) — sans ce détail, le `*` serait lui-même
        compté comme "dernier coup" par `findLastMove` et fausserait la détection.
        """
        pgn = "1. e4 ( 1. Nf3 ) { Trailing Comment } "
        result, _opens, _closes = insertNullMoveBeforeLastComment(pgn)
        assert " Z0 { Trailing Comment } " in result

    def test_does_not_insert_when_ending_is_move_then_comment(self) -> None:
        """Une partie se terminant par coup puis commentaire n'est pas modifiée."""
        pgn = "1. e4 e5 { Trailing Comment } "
        result, _opens, _closes = insertNullMoveBeforeLastComment(pgn)
        assert result == pgn

    def test_matches_chessbase_fixture_bug_pattern(self) -> None:
        """Reproduit, via le fixture réel, le motif coup-variation-commentaire."""
        fixture = (FIXTURES_DIR / "ChessBase Import Issue.pgn").read_text(
            encoding="utf-8"
        )
        broken_game = fixture.split("[Event")[
            3
        ]  # "This does not display correctly" (2 variations)
        body = "{ Leading Comment" + broken_game.split("{ Leading Comment", 1)[1]
        # Dans le pipeline réel (Pgn.createPgnFromHtml), cette fonction s'exécute
        # avant que buildGameResult n'ajoute le terminateur : on le retire ici pour
        # ne pas fausser findLastMove, qui le compterait sinon comme "dernier coup".
        body = body.rsplit("*", 1)[0]

        result, _opens, _closes = insertNullMoveBeforeLastComment(body)

        assert " Z0 " in result
        z0_pos = result.index(" Z0 ")
        trailing_comment_pos = result.index("Trailing Comment - this actually ties")
        assert z0_pos < trailing_comment_pos


class TestEscapeLastNumberInComments:
    """Tests pour `escapeLastNumberInComments`."""

    def test_escapes_comment_ending_in_a_number(self) -> None:
        """Un commentaire finissant par un nombre isolé reçoit un `{ _ }` de garde."""
        pgn = "1. e4 { Comment ending in 5 } *"
        _index, opens, closes = findLastRootComment(pgn)
        result = escapeLastNumberInComments(pgn, opens, closes)
        assert result == "1. e4 { Comment ending in 5 } { _ }  *"

    def test_does_not_escape_comment_not_ending_in_a_number(self) -> None:
        """Un commentaire ne se terminant pas par un nombre n'est pas modifié."""
        pgn = "1. e4 { Ordinary comment } *"
        _index, opens, closes = findLastRootComment(pgn)
        result = escapeLastNumberInComments(pgn, opens, closes)
        assert result == pgn

    def test_skips_sequential_comments(self) -> None:
        """Deux commentaires consécutifs ('} {') n'échappent pas le premier."""
        pgn = "1. e4 { ends in 5 }  { another } *"
        _index, opens, closes = findLastRootComment(pgn)
        result = escapeLastNumberInComments(pgn, opens, closes)
        assert result == pgn


class TestWriteCoursePgnFile:
    """Tests pour `Pgn.writeCoursePgnFile`."""

    def test_writes_new_file_in_overwrite_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode non-incrémental, le fichier est (ré)écrit intégralement."""
        monkeypatch.setattr(settings, "chessable_pgn_cache", tmp_path)
        Pgn.writeCoursePgnFile("118788", "first content", incremental=False)
        Pgn.writeCoursePgnFile("118788", "second content", incremental=False)
        content = (tmp_path / "course" / "118788.pgn").read_text(encoding="utf-8")
        assert content == "second content"

    def test_appends_in_incremental_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode incrémental, chaque écriture complète le fichier existant."""
        monkeypatch.setattr(settings, "chessable_pgn_cache", tmp_path)
        Pgn.writeCoursePgnFile("118788", "first ", incremental=False)
        Pgn.writeCoursePgnFile("118788", "second", incremental=True)
        content = (tmp_path / "course" / "118788.pgn").read_text(encoding="utf-8")
        assert content == "first second"


class TestWriteVariationPgnFile:
    """Tests pour `Pgn.writeVariationPgnFile`."""

    def test_writes_variation_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le fichier PGN de la variation est écrit sous `variation/<id>.pgn`."""
        monkeypatch.setattr(settings, "chessable_pgn_cache", tmp_path)
        Pgn.writeVariationPgnFile("12345", "pgn content")
        content = (tmp_path / "variation" / "12345.pgn").read_text(encoding="utf-8")
        assert content == "pgn content"
