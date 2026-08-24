---
type: ProjectJournal
project: chess_toolbox
updated: 2026-06-28
tags: [python, chess]
---

# Décisions

## 2026-08-24 — Extras `optional-dependencies` plutôt que `dependency-groups` (PEP 735)

Le template `project_template` utilise `[dependency-groups] dev = [...]`
(auto-installé par `uv sync` seul), mais le plan de modernisation impose
explicitement `[project.optional-dependencies]` + `uv add --optional dev <pkg>` :
les dependency-groups PEP 735 ne sont pas installables via `pip install -e .[dev]`
en CI.

**Conséquence :** `uv sync` seul n'installe plus les extras — toute commande
(locale ou CI) doit utiliser `uv sync --all-extras`. Le `ci.yml` copié du
template utilisait `uv sync` nu dans ses 3 jobs ; corrigé en
`uv sync --all-extras` avant même le premier run CI (sinon CI cassée en silence).

## 2026-08-24 — Override mypy legacy (chessable_to_pgn) : `ignore_errors` plutôt que flags partiels

L'override pré-existant pour `chessable_to_pgn.*` (module vendor tiers, dette
technique scopée en Phase 4b) ne désactivait que `disallow_untyped_defs`,
`disallow_untyped_calls`, `check_untyped_defs`. Il ne couvrait pas
`disallow_incomplete_defs` (toujours actif via `strict = true`), qui gouverne
le message « missing a return type annotation » sur les fonctions partiellement
typées — d'où 36 erreurs mypy non supprimées malgré un nom de module identique
à l'entrée de l'override (vérifié via `mypy --verbose`).

**Décision :** remplacer les 3 flags partiels par `ignore_errors = true`,
l'idiome standard pour une exemption complète d'un module legacy. Correspond
à l'intention d'origine (exemption totale en attendant le vrai typage en
Phase 4b) sans élargir le périmètre de Phase 1.

## 2026-08-24 — `okf-base.yaml` : `status_values` retiré des types sans propriété `status`

`status_values: false` était déclaré sur `ProjectDescription`, `ProjectStandards`
et `ProjectJournal`, alors qu'aucun de ces types ne déclare `status` dans
`required`/`optional`. okflint rejette toute `_values` déclarée pour une
propriété non déclarée (`ManifestError`), et `status_values` doit de toute
façon être une liste de chaînes, pas un booléen.

**Décision :** supprimer la clé sur ces 3 types (absence = pas de vocabulaire
contrôlé, ce qui est correct puisque la propriété n'existe pas pour eux).
Seul `ProjectLifeCycle` (qui déclare `status` en required) garde
`status_values: [active, archived]`.
