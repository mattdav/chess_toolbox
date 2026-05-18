
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

**Méthode normale :**

```bash
uv run chess_toolbox chessable-login
```

Une fenêtre Chrome for Testing s'ouvre. Se connecter manuellement, le script
sauvegarde les cookies et se ferme.

**Si Cloudflare bloque la connexion automatisée :**

1. Se connecter à Chessable dans son navigateur habituel (Chrome/Firefox).
2. Exporter les cookies avec l'extension [Cookie-Editor](https://cookie-editor.com/)
   au format JSON.
3. Importer dans Chrome for Testing :

```bash
uv run chess_toolbox chessable-import-cookies cookies.json
```

Les cookies sont sauvegardés dans le profil CfT et réutilisés automatiquement.


## Acknowledgements

- [README generator](https://readme.so/fr)
- [chessable-to-pgn](https://github.com/JohnDeMastri/chessable-to-pgn) (John DeMastri)
