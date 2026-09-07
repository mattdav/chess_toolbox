---
type: ProjectStandards
project: chess_toolbox
updated: 2026-08-26
tags: [python, chess]
---

# CLAUDE.md — chess_toolbox (projet racine)

Ce fichier guide Claude Code pour tous les travaux sur le projet `chess_toolbox`.

## Vision du projet

`chess_toolbox` est une boîte à outils CLI d'**utilitaires d'administration** pour les échecs. Elle centralise deux sous-outils accessibles via une interface de commande unique :

| Commande CLI | Module source | Rôle |
| --- | --- | --- |
| `uv run chess_toolbox split-pgn` | `bin/split_pgn/` | Découpe un PGN d'ouvertures en fichiers par variante |
| `uv run chess_toolbox extract-chessable` | `bin/chessable_to_pgn/` | Exporte un cours Chessable au format PGN |

Ce projet ne contient **pas** de logique d'analyse ou de coaching — ces fonctionnalités sont dans le projet séparé `chess_coach` (`../chess_coach`).

## Structure du projet

```text
chess_toolbox/
├── CLAUDE.md                   # Ce fichier
├── pyproject.toml              # Dépendances et config outils (ruff, mypy, pytest)
├── .env                        # Secrets locaux (jamais committé — voir .env.example)
├── .env.example                # Template des variables d'environnement
├── config.yaml                 # Configuration non-sensible (chemins, seuils)
├── config.yaml.example         # Template de config.yaml
├── src/chess_toolbox/
│   ├── __init__.py
│   ├── __main__.py             # CLI unifié (argparse + sous-commandes)
│   ├── config/
│   │   ├── settings.py         # Chargement centralisé de .env + config.yaml
│   │   └── __init__.py
│   ├── bin/
│   │   ├── split_pgn/
│   │   │   ├── CLAUDE.md
│   │   │   ├── __init__.py     # expose main()
│   │   │   └── core.py         # Logique de découpe PGN
│   │   └── chessable_to_pgn/
│   │       ├── __init__.py     # expose main()
│   │       ├── core.py         # Entrée principale (adapté de chessable-to-pgn.py)
│   │       ├── command_line.py
│   │       ├── pgn_writer.py
│   │       ├── web_fetch.py
│   │       ├── utilities.py
│   │       ├── License.txt     # MIT, attribution upstream
│   │       └── ReadMe.md       # Doc upstream adaptée
│   └── py.typed
└── tests/
```

## Commandes de développement

```bash
# Lancer un sous-outil
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --depth 2
uv run chess_toolbox extract-chessable --course-id 12345

# Qualité du code (via Invoke — tasks.py à la racine du répertoire parent)
inv lint          # ruff check --fix + ruff format + mypy
inv clean         # nettoyage des artefacts de build

# Vérifications individuelles
uv run ruff check src/
uv run ruff format src/
uv run mypy src/
uv run pytest
```

## Standards de qualité (OBLIGATOIRES)

### Type hints et beartype

- Toutes les fonctions **publiques** ont des type hints complets
- Le décorateur `@beartype` est appliqué sur toutes les fonctions publiques
- `uv run mypy src/` doit passer avec 0 erreur (mode `strict = true`)

### Linting

- `uv run ruff check src/` doit passer avec 0 warning
- `uv run ruff format src/` avant tout commit
- `uv run inv lint` valide les trois vérifications en séquence

### Tests

- Couverture minimale : 80 % (`fail_under = 80`)
- Tests unitaires dans `tests/unit/`, tests d'intégration dans `tests/integration/`
- Les doctests dans les modules sont activés (`--doctest-modules`)

### Documentation

- Toutes les fonctions publiques ont une docstring au format Google style
- Les paramètres, retours et exceptions sont documentés

## Configuration (architecture)

La configuration est séparée en deux couches :

### `.env` — Secrets (jamais dans git)

```text
STOCKFISH_PATH=C:\...\stockfish.exe
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
LICHESS_USERNAME=pseudo_lichess
PLAYER_ELO=1650
```

### `config.yaml` — Paramètres non-sensibles

```yaml
chess_coach:
  max_games: 50
  stockfish_depth: 18
  max_daily_minutes: 45

split_pgn:
  default_depth: 1
  default_output_suffix: "_split"

chessable_to_pgn:
  output_dir: data/pgn/chessable        # dossier de sortie des PGN
  html_cache_dir: data/cache/chessable  # cache des pages HTML (évite re-téléchargements)
  fetch_mode: incremental               # "incremental" | "all" | "cached"
```

### `src/chess_toolbox/config/settings.py`

Module centralisé qui charge `.env` via `python-dotenv` et `config.yaml` via `pyyaml`, expose des dataclasses typées pour la configuration de chaque sous-outil.

## Dépendances externes clés

- **python-chess** : manipulation des PGN
- **beartype** : validation runtime des types
- **python-dotenv** : chargement du `.env`
- **pyyaml** : lecture de `config.yaml`

Ce projet n'a **pas** de dépendance vers caissAI ni vers l'API Claude — ces dépendances appartiennent à `chess_coach`.

## chessable_to_pgn — notes spécifiques

`chessable_to_pgn` (`bin/chessable_to_pgn/`) est une adaptation du projet open source
[chessable-to-pgn](https://github.com/demastri/chessable-to-pgn) par John DeMastri
(MIT License, `License.txt` conservé). Le code a divergé irréversiblement de
l'upstream (renommage snake_case, typage complet, config pydantic, `WebFetch`
réécrit) : ce n'est plus un portage à synchroniser, mais du code source ordinaire
du projet.

### Configuration Selenium / Chrome for Testing

Chrome normal refuse d'être piloté par Selenium si une instance utilisateur est
déjà ouverte (il délègue silencieusement au processus existant, qui n'a pas les
flags Selenium), ce qui produit :

```text
session not created: Chrome failed to start: crashed.
(session not created: DevToolsActivePort file doesn't exist)
```

Utiliser **Chrome for Testing (CfT)**, binaire isolé dédié à l'automatisation :

1. Télécharger **chrome** et **chromedriver** (`win64`, `Stable`) depuis
   `https://googlechromelabs.github.io/chrome-for-testing/`
2. Extraire dans `C:/tools/chrome-for-testing/`
3. Dans `.env` :

   ```text
   CHROME_BINARY_PATH=C:/tools/chrome-for-testing/chrome.exe
   CHROME_PROFILE_DIR=C:/tools/chrome-for-testing/user-data
   CHESSABLE_HEADLESS=false
   CHESSABLE_DEBUG_PORT=0
   ```

4. Premier lancement : se connecter à Chessable manuellement dans la fenêtre CfT.
   Les cookies sont sauvegardés dans `CHROME_PROFILE_DIR` et réutilisés ensuite.

Le mode `CHESSABLE_DEBUG_PORT > 0` (remote-debugging sur un Chrome déjà lancé)
ne fonctionne pas sous Windows : un Chrome déjà ouvert délègue au singleton
existant sans jamais ouvrir de socket sur le port demandé. En pratique, rester
en `CHESSABLE_DEBUG_PORT=0` avec CfT.

### Limitations connues

1. **Authentification Chessable** : certains cours nécessitent d'être connecté —
   utiliser CfT en mode non-headless pour la première connexion manuelle.
2. **Rate limiting** : le cache HTML local (`html_cache_dir`) évite les
   re-téléchargements en cas de blocage Chessable.
3. **App-Bound Encryption** (Chrome 127+) : Chrome normal chiffre ses cookies
   avec un mécanisme lié au compte Windows ; CfT gère ses propres cookies dans
   `CHROME_PROFILE_DIR` sans ce mécanisme, donc sans interférence.

### Tests spécifiques

Mocker les appels HTTP (`requests`, Selenium) pour tester `generateCoursePGNs`
et la génération PGN sans accès réseau ni navigateur.

### Oracle de comptage et stabilisation du rendu

Chaque page de cours expose, par chapitre, un compteur `div.variationStats`
(ex. `"0/14 variations"`) donnant le nombre de variations trouvées vs attendues.
Un chapitre incomplet déclenche une nouvelle tentative en forçant un accès
réseau (jusqu'à 3 tentatives), plutôt qu'une mise en cache silencieuse d'une
page tronquée. L'attente de chargement Selenium attend désormais que le
nombre d'éléments soit **stable** (pas juste présent) avant mise en cache,
pour éviter de figer une page partiellement rendue.

## Règles importantes pour Claude Code

1. **Ne jamais committer `.env` ou `config.cfg` contenant de vraies clés API**
2. **Toujours utiliser `@beartype` sur les nouvelles fonctions publiques**
3. **Toujours vérifier `inv lint` (depuis le répertoire racine parent) avant de valider un fichier**
4. **Les imports du module `chessable_to_pgn` doivent être relatifs** (module tiers adapté)
5. **chess_toolbox ne contient que des utilitaires** : toute logique d'analyse ou de coaching va dans `chess_coach`
6. **Langue** : code et commentaires en français, identifiants Python en anglais (snake_case)
