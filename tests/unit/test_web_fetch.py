"""Tests pour la détection de page publique de `chessable_to_pgn.web_fetch`."""

from pathlib import Path

from chess_toolbox.bin.chessable_to_pgn.web_fetch import _is_public_page

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_is_public_page_detects_public_html() -> None:
    """Le HTML de la page d'accueil publique est reconnu comme tel."""
    html = (FIXTURES_DIR / "chessable_public_page.html").read_text(encoding="utf-8")
    assert _is_public_page(html) is True


def test_is_public_page_rejects_authenticated_html() -> None:
    """Un HTML de contenu authentifié n'est pas confondu avec la page publique."""
    html = "<html><head><title>Course Dashboard</title></head><body></body></html>"
    assert _is_public_page(html) is False
