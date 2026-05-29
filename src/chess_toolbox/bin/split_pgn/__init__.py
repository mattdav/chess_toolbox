"""Outil de découpe d'arbres d'ouvertures PGN en fichiers par variante.

Compatible ChessBase : chaque fichier généré contient le FEN de départ.
"""

from .core import main

__all__ = ["main"]
