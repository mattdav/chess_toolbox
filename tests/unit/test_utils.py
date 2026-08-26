"""Tests pour `chess_toolbox.utils`."""

import pytest

from chess_toolbox.utils import get_package_dir


class TestGetPackageDir:
    """Tests pour `get_package_dir`."""

    def test_returns_existing_subpackage_dir(self) -> None:
        """Un sous-package existant retourne son dossier absolu."""
        path = get_package_dir("config")
        assert path.is_dir()
        assert path.name == "config"

    def test_raises_on_unknown_subpackage(self) -> None:
        """Un sous-package inexistant lève `ModuleNotFoundError`."""
        with pytest.raises(ModuleNotFoundError):
            get_package_dir("does_not_exist")
