# chess_toolbox

Boîte à outils pour manipuler et gérer des bases PGN d'ouvertures d'échecs.

## Authors

- [@mattdav](https://github.com/mattdav)

## Badges

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

## Installation

```bash
uv sync
```

Copier `.env.example` vers `.env` et renseigner les chemins Chrome for Testing :

```env
CHROME_BINARY_PATH=C:/tools/chrome-for-testing/chrome.exe
CHROME_PROFILE_DIR=C:/tools/chrome-for-testing/user-data
CHESSABLE_HTML_CACHE=src/chess_toolbox/data/courses/html/
CHESSABLE_PGN_CACHE=src/chess_toolbox/data/courses/pgn/
```

## Commandes

### split-pgn — Découpage d'un arbre PGN

Découpe un fichier PGN d'ouvertures en fichiers séparés par variante.

```bash
# Lister les variantes disponibles après 1.e4
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --list

# Découper à profondeur 2 après 1.e4
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --depth 2 --output out/
```

### extract-chessable — Export d'un cours Chessable en PGN

```bash
uv run chess_toolbox extract-chessable -courses 12345
uv run chess_toolbox extract-chessable -courses 12345 67890
uv run chess_toolbox extract-chessable -interactive
```

#### Authentification

Le scraping des pages de cours utilise `curl_cffi` (impersonation TLS Chrome)
plutôt qu'un navigateur automatisé — plus fiable face à Cloudflare.

**Première utilisation :**

1. Se connecter à Chessable dans son navigateur habituel (Chrome/Firefox).
2. Exporter les cookies avec l'extension [Cookie-Editor](https://cookie-editor.com/)
   au format JSON.
3. Enregistrer les cookies :

```bash
uv run chess_toolbox chessable-import-cookies cookies.json
```

Les cookies sont sauvegardés dans `./chessable_cookies.json` (chemin configurable
via `CHESSABLE_COOKIES_FILE` dans `.env`). À renouveler quand la session expire
(typiquement après quelques semaines).

> Les pages de variations utilisent encore Selenium. `chessable-login` reste
> disponible si CfT fonctionne sur l'environnement cible.

## Acknowledgements

- [README generator](https://readme.so/fr)
- [chessable-to-pgn](https://github.com/JohnDeMastri/chessable-to-pgn) (John DeMastri)
