"""Configuration typée du projet, chargée depuis l'environnement et `.env`."""

import enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WindowMode(enum.Enum):
    """Mode d'affichage de la fenêtre Firefox pour l'automatisation Chessable."""

    #: Fenêtre réelle (pas de ``--headless``) mais positionnée hors de tout
    #: écran physique après sa construction — invisible pour l'utilisateur
    #: sans les particularités de rendu/fingerprint du vrai mode headless.
    OFFSCREEN = "offscreen"
    #: Navigateur sans rendu de fenêtre (``--headless``).
    HEADLESS = "headless"
    #: Fenêtre normale, visible à l'écran.
    VISIBLE = "visible"


class Settings(BaseSettings):
    """Paramètres d'automatisation Chessable (navigateur, profils, caches).

    Les champs correspondent aux variables d'environnement de même nom en
    MAJUSCULES (`firefox_binary_path` -> `FIREFOX_BINARY_PATH`), chargées
    depuis `.env` à la racine du projet.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    base_chessable_url: str = "https://www.chessable.com/"
    firefox_binary_path: str = ""
    firefox_automation_profile_dir: str = "C:/tools/firefox-automation-profile"
    geckodriver_path: str = ""
    chessable_html_cache: Path = Path("./html")
    chessable_pgn_cache: Path = Path("./pgn")
    chessable_window_mode: WindowMode = WindowMode.OFFSCREEN


settings = Settings()
