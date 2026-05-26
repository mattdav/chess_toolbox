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

Chessable utilise Cloudflare Bot Management. La méthode recommandée est le
mode **CDP** (Chrome DevTools Protocol) : le script se connecte à Chrome
normal déjà ouvert, ce qui contourne toute détection.

**Configuration initiale (une seule fois) :**

```bash
uv run chess_toolbox chessable-start-browser
```

Une fenêtre Chrome s'ouvre sur la page de connexion Chessable. Se connecter,
puis ajouter dans `.env` :

```env
CHESSABLE_DEBUG_PORT=9222
```

La session est mémorisée dans le profil dédié (`CHROME_AUTOMATION_PROFILE_DIR`,
défaut `C:/tools/chrome-automation-profile`). Les runs suivants ne demandent
plus de connexion manuelle.

**Usage courant :**

Lancer Chrome avec le port de debug, puis démarrer l'export :

```bash
uv run chess_toolbox chessable-start-browser
uv run chess_toolbox extract-chessable -courses 12345
```

> **Variables `.env` optionnelles :**
> - `CHROME_REGULAR_BINARY_PATH` — chemin vers `chrome.exe` si non détecté automatiquement
> - `CHROME_AUTOMATION_PROFILE_DIR` — répertoire du profil dédié (défaut : `C:/tools/chrome-automation-profile`)

## Acknowledgements

- [README generator](https://readme.so/fr)
- [chessable-to-pgn](https://github.com/JohnDeMastri/chessable-to-pgn) (John DeMastri)
