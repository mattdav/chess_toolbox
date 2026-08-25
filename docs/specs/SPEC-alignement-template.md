---
type: Spec
id: SPEC-alignement-template
title: "Alignement de chess_toolbox sur project_template"
description: "Rattacher chess_toolbox, créé avant le template, à l'infrastructure qualité et documentaire standard"
status: implemented # draft | accepted | implemented | superseded
superseded-by:
work-item:
tags: [tooling, ci, documentation]
timestamp: 2026-08-24
perimeter: project
audience: []
---

# Alignement de chess_toolbox sur project_template

## Objectif

`chess_toolbox` a été créé avant l'existence du template cookiecutter
`mattdav/project_template`. Il n'a pas de `.cruft.json`, pas d'infrastructure
pre-commit, pas de corpus documentaire typé OKF, et sa structure `src/` diverge
de la convention `bin/config/data/log`. Cette spec cadre le chantier de mise à
niveau qui aligne le projet sur le template sans en changer le comportement
fonctionnel.

## Périmètre

### Inclus

- Rattachement cruft (`.cruft.json`, sans `cruft update` automatique).
- Scaffolding qualité : pre-commit, CI unifiée, commitizen, tâches invoke.
- Documentation et conformité OKF (`docs/code`, `docs/specs`, `docs/fixes`,
  `docs/plans`, fichiers réservés `index.md`/`log.md`).
- Structure `src/` (`utils.py`, `data/__init__.py`, `config/settings.py`
  via pydantic-settings) et complétion de `.claude/`.
- Dette technique du module `bin/chessable_to_pgn/` : renommages, typage
  strict, réécriture ciblée de `WebFetch`, détection robuste de
  l'expiration de session.

### Non-objectifs

Le sous-outil `bin/split_pgn/` n'est pas retouché au-delà des correctifs de
scaffolding déjà nécessaires pour `inv lint`. Le mécanisme wiki du template
(`use_wiki=no`) et la publication PyPI (`publish_pypi=no`) ne sont pas
activés : décisions de cadrage actées avant le démarrage du chantier.

## Spécification fonctionnelle

Le chantier DOIT préserver le comportement observable de
`chess_toolbox extract-chessable` à chaque étape intermédiaire (Phase 4a en
particulier : aucun changement de comportement). Il DOIT converger vers
`uv run inv lint` et `uv run okflint validate --manifest okf-base.yaml .` à
zéro erreur à la fin de chaque phase. Le module `chessable_to_pgn` PEUT rester
sous exemption mypy tant que sa Phase de typage (4b) n'est pas réalisée.

## Choix et contraintes

Rattachement cruft sans `cruft update` : le projet a divergé bien au-delà de
ce que cruft sait fusionner automatiquement — l'écart est comblé manuellement,
phase par phase. `type` reste en `required` sur tous les types OKF du projet,
y compris les quatre ajoutés en Phase 2, par cohérence interne (voir
`.claude/DECISIONS.md`) même là où le template ne l'exige pas.

## Critères d'acceptation

- [x] `.cruft.json` présent et projet suivable par `inv update`.
- [x] `uv run inv lint` passe à zéro (Phase 1).
- [x] `uv run okflint validate --manifest okf-base.yaml .` passe (Phase 2).
- [ ] `src/` aligné sur la convention `bin/config/data/log` (Phase 3).
- [ ] Module `chessable_to_pgn` sans exemption mypy, `WebFetch` réécrit en
      `ChessableFetcher`, détection d'authentification robuste (Phase 4).
