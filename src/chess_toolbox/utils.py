"""Fonctions utilitaires partagées par l'application.

Examples:
    >>> from chess_toolbox.utils import get_package_dir
    >>> path = get_package_dir("config")
    >>> path.is_dir()
    True
"""

import importlib.resources
from pathlib import Path


def get_package_dir(subpackage: str) -> Path:
    """Retourne le chemin absolu d'un sous-package.

    Utilise importlib.resources.files (Python 3.11+) pour résoudre les
    chemins au sein du package installé, qu'il tourne depuis les sources
    ou depuis un wheel.

    Args:
        subpackage: Nom du sous-package (ex. "config", "data", "log").

    Returns:
        Chemin absolu vers le dossier du sous-package.

    Raises:
        ModuleNotFoundError: Si le sous-package n'existe pas.

    Examples:
        >>> p = get_package_dir("config")
        >>> p.name
        'config'
    """
    package_name = __name__.split(".")[0]
    ref = importlib.resources.files(f"{package_name}.{subpackage}")
    return Path(str(ref))
