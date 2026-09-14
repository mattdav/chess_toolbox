# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html


# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

from sphinx.application import Sphinx

# Le package est exposé via src/ : c'est ce dossier qu'il faut ajouter au
# path pour qu'autodoc puisse importer le package sous son vrai nom.
sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "chess_toolbox"
copyright = "2025, Matthieu Daviaud"
author = "Matthieu Daviaud"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.githubpages",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
]

# Docstrings au format Google (cf. CONTRIBUTING.md)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
# Émet les attributs de section "Attributes:" comme champs :ivar: plutôt que
# comme directives .. attribute:: séparées, pour éviter les doublons avec
# autodoc qui documente déjà ces mêmes attributs depuis les annotations de classe.
napoleon_use_ivar = True

templates_path = ["_templates"]
exclude_patterns = []

# bs4.element._RawAttributeValue est une annotation interne à bs4 que
# sphinx_autodoc_typehints ne peut pas résoudre — rien de corrigeable côté
# chess_toolbox.
suppress_warnings = ["sphinx_autodoc_typehints.forward_reference"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# Aucun asset statique par défaut : déclarer un dossier _static/ inexistant
# fait émettre un avertissement à chaque build. À repasser à ["_static"] le
# jour où le dossier est créé.
html_static_path: list[str] = []


# Pour gérer __main__ spécifiquement
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "special-members": "__init__",
}


def _run_apidoc(app: Sphinx) -> None:
    """Génère les pages d'API avant chaque build, en local comme en CI."""
    from pathlib import Path

    from sphinx.ext.apidoc import main

    package = Path(__file__).parent.parent.parent / "src" / "chess_toolbox"
    output = Path(__file__).parent / "api"
    main(["--force", "--separate", "--module-first", "-o", str(output), str(package)])


def setup(app: Sphinx) -> None:
    """Enregistre la génération d'API sur l'événement `builder-inited`."""
    app.connect("builder-inited", _run_apidoc)
