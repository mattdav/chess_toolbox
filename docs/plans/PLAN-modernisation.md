---
type: Plan
id: PLAN-modernisation
title: "Modernisation chess_toolbox — alignement sur project_template"
description: "Mode opératoire en cinq phases pour rattacher chess_toolbox au template et résorber sa dette technique"
status: active # draft | active | done | deprecated
implements: SPEC-alignement-template # SPEC-xxx ou FIX-xxx — obligatoire
tags: [tooling, ci, documentation, chessable]
timestamp: 2026-08-24
perimeter: project
audience: []
---

# Modernisation chess_toolbox — alignement sur project_template

## Périmètre

Ce plan implémente `SPEC-alignement-template` en cinq phases séquentielles,
chacune vérifiée avant d'enchaîner sur la suivante.

## Étapes

### 0. Rattachement cruft — réalisé

- Fichiers cibles : `.cruft.json`
- Action : `cruft link` vers `project_template` (HEAD), sans `cruft update`.
- Vérification : `.cruft.json` committé, rapport `cruft diff` classé en trois
  catégories (absents, divergents, propres au projet).

### 1. Scaffolding qualité — réalisé

- Fichiers cibles : `.pre-commit-config.yaml`, `tasks.py`, `pyproject.toml`,
  `.github/workflows/ci.yml`, `CHANGELOG.md`, `CONTRIBUTING.md`.
- Action : infrastructure pre-commit, CI unifiée, commitizen, tâches invoke.
- Vérification : `uv run inv lint` passe à zéro.

### 2. Documentation et conformité OKF — réalisé

- Fichiers cibles : `docs/code/`, `docs/specs/`, `docs/fixes/`, `docs/plans/`,
  `docs/_templates/`, `index.md`, `log.md`, `okf-base.yaml`, `.gitignore`.
- Action : renommage `docs/source` → `docs/code`, arborescence documentaire
  typée OKF, types `Spec`/`Fix`/`Plan`/`Command` ajoutés au profil.
- Vérification : `uv run okflint validate --manifest okf-base.yaml .` passe,
  `uv run inv docs` construit sans warning bloquant.

### 2bis. Formalisation documentaire — en cours

- Fichiers cibles : ce document, `SPEC-alignement-template`,
  `SPEC-session-chessable`, `FIX-cache-html-empoisonne`, `log.md`.
- Action : faire entrer le chantier lui-même, et l'incident du cache HTML
  empoisonné, dans le corpus documentaire.
- Vérification : `uv run okflint validate --manifest okf-base.yaml .` passe,
  aucun lien cassé entre les quatre documents.

### 3. Structure `src/` et contexte Claude

- Fichiers cibles : `src/chess_toolbox/data/__init__.py`,
  `src/chess_toolbox/utils.py`, `src/chess_toolbox/config/settings.py`,
  `src/chess_toolbox/bin/chessable_to_pgn/ConfigData.py`, `.claude/`.
- Action : `config/settings.py` via pydantic-settings, `ConfigData.py`
  transformé en façade déléguante, suppression du `py.typed` dupliqué,
  complétion de `.claude/` (`settings.json`, `rules/`, `commands/doc-new.md`,
  `agents/`, `skills/`, `DECISIONS-archive.md`). `CLAUDE.md` reste à la racine.
- Vérification : `uv run inv lint` passe, `uv run chess_toolbox
  extract-chessable -courses 5193` fonctionne à l'identique.

### 4a. Renommages `chessable_to_pgn` — réalisé

- Fichiers cibles : `WebFetch.py`, `CommandLine.py`, `Utilities.py`, `Pgn.py`,
  `ConfigData.py`, `chessable_cookies.json`, `pyproject.toml`.
- Action : renommages PascalCase → snake_case (`Pgn.py` → `pgn_writer.py` pour
  éviter le conflit de casse Windows avec `pgn/`), suppression de
  `ConfigData.py` et du code mort `curl_cffi`.
- Vérification : `uv run chess_toolbox extract-chessable -courses 5193`
  fonctionne à l'identique, aucun changement de comportement.

### 4b. Typage `chessable_to_pgn` — réalisé

- Fichiers cibles : `web_fetch.py`, `pgn_writer.py`, `command_line.py`,
  `utilities.py`, `core.py`, `pyproject.toml`.
- Action : type hints complets, `@beartype`, docstrings Google, constantes de
  mode en `enum.Enum`, suppression du bloc `[[tool.mypy.overrides]]`.
- Vérification : `uv run inv lint` passe à zéro sans exemption mypy.

### 4c. Réécriture de `WebFetch` — réalisé

- Fichiers cibles : `web_fetch.py`, `command_line.py`,
  `src/chess_toolbox/__main__.py`, `config/settings.py`, `.env.example`.
- Action : `ChessableFetcher` en gestionnaire de contexte (un seul navigateur
  par run), `argparse` en remplacement du parsing manuel, `CHESSABLE_WINDOW_MODE`
  à trois valeurs (`offscreen` par défaut, `headless`, `visible`).
- Vérification : extraction complète fonctionnelle, une seule fenêtre Firefox
  ouverte sur toute la durée du run, tableau comparatif des trois modes.

### 4d. Détection d'authentification

- Fichiers cibles : `web_fetch.py`, `src/chess_toolbox/__main__.py`,
  `tests/fixtures/chessable_public_page.html`.
- Action : détection par comparaison d'URL, `ensure_session()` en preflight,
  exception `ChessableAuthError`, option `--relogin`, suppression de
  `_is_public_page`/`_warn_session_expired` (voir `FIX-cache-html-empoisonne`).
- Vérification : session valide → extraction normale ; session invalidée →
  message explicite, code de sortie 2, aucun fichier écrit.

## Mise à jour documentaire

- [x] `README.md` du produit mis à jour si le fonctionnement change (Phase 1)
- [ ] Statut de `SPEC-alignement-template` passé à `implemented` une fois la
      Phase 4 terminée
- [ ] Statut de `SPEC-session-chessable` passé à `implemented` une fois la
      Phase 4d terminée
- [x] `.env.example` documenté pour `CHESSABLE_WINDOW_MODE` (Phase 4c)

## Vérification finale

`uv run inv lint` et `uv run okflint validate --manifest okf-base.yaml .`
passent à zéro sur l'ensemble du dépôt, et `uv run chess_toolbox
extract-chessable -courses 5193` produit un résultat identique à celui
d'avant le chantier, en dehors des gains de performance et de fiabilité
attendus des Phases 4c et 4d.
