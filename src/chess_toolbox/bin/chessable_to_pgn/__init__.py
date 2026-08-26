"""Adaptateur du projet chessable-to-pgn (John DeMastri, MIT) pour chess_toolbox.

Exporte les cours Chessable au format PGN.

Configuration via variables d'environnement (voir .env.example) :
    FIREFOX_BINARY_PATH            — chemin vers l'exécutable Firefox
    FIREFOX_AUTOMATION_PROFILE_DIR — répertoire du profil dédié
    CHESSABLE_HTML_CACHE           — répertoire de cache HTML (défaut : ./html/)
    CHESSABLE_PGN_CACHE            — répertoire de sortie PGN (défaut : ./pgn/)
"""

from .core import main

__all__ = ["main"]
