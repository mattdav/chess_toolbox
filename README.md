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

Copier `.env.example` vers `.env` et renseigner les chemins :

```env
FIREFOX_AUTOMATION_PROFILE_DIR=C:/tools/firefox-automation-profile
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
mode **Firefox avec profil persistant** : le script utilise Firefox (votre
navigateur réel) avec un profil dédié — Cloudflare voit un navigateur de
confiance avec une session active.

**Configuration initiale (une seule fois) :**

```bash
uv run chess_toolbox chessable-start-browser
```

Une fenêtre Firefox s'ouvre sur la page de connexion Chessable. Se connecter,
puis **fermer Firefox complètement**. La session est mémorisée dans le profil
dédié (`FIREFOX_AUTOMATION_PROFILE_DIR`, défaut `C:/tools/firefox-automation-profile`).

**Usage courant :**

```bash
uv run chess_toolbox extract-chessable -courses 12345
```

Aucune connexion manuelle n'est requise après le premier login.

**Variables `.env` optionnelles :**

- `FIREFOX_BINARY_PATH` — chemin vers `firefox.exe` si non détecté automatiquement
- `FIREFOX_AUTOMATION_PROFILE_DIR` — répertoire du profil dédié (défaut : `C:/tools/firefox-automation-profile`)
- `GECKODRIVER_PATH` — chemin vers GeckoDriver si non géré automatiquement par Selenium Manager

## Acknowledgements

- [README generator](https://readme.so/fr)
- [chessable-to-pgn](https://github.com/JohnDeMastri/chessable-to-pgn) (John DeMastri)
