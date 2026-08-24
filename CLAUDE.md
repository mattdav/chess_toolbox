---
type: ProjectStandards
project: chess_toolbox
updated: 2026-06-28
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
│   │       ├── CLAUDE.md
│   │       ├── __init__.py     # expose main()
│   │       ├── core.py         # Entrée principale (adapté de chessable-to-pgn.py)
│   │       ├── CommandLine.py
│   │       ├── ConfigData.py
│   │       ├── Pgn.py
│   │       ├── WebFetch.py
│   │       └── Utilities.py
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
  output_dir: data/pgn
```

### `src/chess_toolbox/config/settings.py`

Module centralisé qui charge `.env` via `python-dotenv` et `config.yaml` via `pyyaml`, expose des dataclasses typées pour la configuration de chaque sous-outil.

## Dépendances externes clés

- **python-chess** : manipulation des PGN
- **beartype** : validation runtime des types
- **python-dotenv** : chargement du `.env`
- **pyyaml** : lecture de `config.yaml`

Ce projet n'a **pas** de dépendance vers caissAI ni vers l'API Claude — ces dépendances appartiennent à `chess_coach`.

## Règles importantes pour Claude Code

1. **Ne jamais committer `.env` ou `config.cfg` contenant de vraies clés API**
2. **Toujours utiliser `@beartype` sur les nouvelles fonctions publiques**
3. **Toujours vérifier `inv lint` (depuis le répertoire racine parent) avant de valider un fichier**
4. **Les imports du module `chessable_to_pgn` doivent être relatifs** (module tiers adapté)
5. **chess_toolbox ne contient que des utilitaires** : toute logique d'analyse ou de coaching va dans `chess_coach`
6. **Langue** : code et commentaires en français, identifiants Python en anglais (snake_case)
