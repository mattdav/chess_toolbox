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

## 2026-08-24 — `okf-base.yaml` : `type` gardé en `required` sur Command/Spec/Fix/Plan (divergence du template)

Le template déclare ces 4 nouveaux types sans `type` dans `required` (ex.
`Spec: required: [id, title, description, status, timestamp, perimeter]`),
alors que les 4 types déjà présents dans le projet (`ProjectDescription`,
`ProjectStandards`, `ProjectLifeCycle`, `ProjectJournal`) l'exigent tous.
Les modèles copiés (`docs/_templates/spec.md`, `fix.md`, `plan.md`, et
`.claude/commands/doc-new.md` côté template) portent pourtant bien un champ
`type: Spec` / `type: Fix` / `type: Plan` / `type: Command` en frontmatter.

**Décision :** garder `type` en `required` sur les 4 nouveaux types, pour
rester cohérent avec la convention déjà en place dans ce projet plutôt que de
suivre le template au pied de la lettre. `hygiene.unknown_fields: off`
rendait les deux options valides sans erreur okflint ; le choix est une
question de cohérence interne, pas de contrainte technique.

## 2026-08-25 — `Settings.geckodriver_path` modélisé mais non exposé par la façade `ConfigData.py`

`geckodriver_path` fait partie du périmètre explicite de `config/settings.py`
(Phase 3), mais rien dans `ConfigData.py` ni ailleurs ne le consomme
aujourd'hui : `WebFetch.py` lit toujours `GECKODRIVER_PATH` directement via
`os.environ.get(...)`, et ce module reste intouché en Phase 3 (réécriture
prévue Phase 4b/4c).

**Décision :** ne pas ajouter de constante `GECKODRIVER_PATH` inutilisée dans
la façade `ConfigData.py` — ce serait du code mort tant que `WebFetch.py`
n'a pas été migré. `settings.geckodriver_path` reste disponible pour la
Phase 4b/4c, qui le consommera directement depuis `config.settings`.

## 2026-08-25 — Commit scindé dans le submodule `chessable_to_pgn` : uniquement `ConfigData.py`

Le submodule `src/chess_toolbox/bin/chessable_to_pgn` portait déjà, avant
cette session, des modifications non liées à la Phase 3 (`CommandLine.py`,
`Utilities.py`, `WebFetch.py`, `ReadMe.md`, suppressions/ajouts de fichiers)
issues d'un travail antérieur non commité.

**Décision :** committer dans le submodule uniquement `ConfigData.py` (seul
fichier touché par la Phase 3), en laissant les autres fichiers du submodule
dans leur état non commité — même logique que pour les fichiers non liés du
dépôt parent (cf. Phase 2). Le pointeur de submodule mis à jour dans le
dépôt parent ne référence donc que ce commit ciblé.

## 2026-08-25 — Commit Phase 4a dans le submodule : état courant plutôt que stash

Les renommages `git mv` de la Phase 4a (`CommandLine.py`, `Utilities.py`,
`WebFetch.py`) portaient sur des fichiers qui avaient déjà, avant cette
session, des modifications non liées non commitées (18 à 85 lignes chacun,
issues d'un travail antérieur). `Pgn.py` seul était propre.

**Décision :** contrairement au commit isolé de la Phase 3 (`ConfigData.py`
seul), ici committer directement l'état courant (déjà dirty) des fichiers
touchés par la Phase 4a, sans tentative de `git stash`/`git mv`/`git stash
pop`. Un stash aurait produit un patch référençant l'ancien nom de fichier
et l'ancien contenu ; le rejouer après un `git mv` + edits risquait un
conflit silencieux ou une perte de contenu difficile à détecter. Le contenu
non lié pré-existant (`ReadMe.md`, `chessable-to-pgn.py` supprimé, `img.png`
supprimé) reste non commité, comme pour la Phase 3.

**Conséquence :** le commit Phase 4a peut contenir, en plus des changements
de la Phase 4a proprement dite, d'éventuelles modifications antérieures déjà
présentes dans les fichiers renommés. Aucune n'a été identifiée comme
fonctionnellement significative lors de la relecture des diffs avant commit.

## 2026-08-25 — Scission du bloc `[[tool.mypy.overrides]]` : `split_pgn.core` isolé

Le bloc `ignore_errors = true` exemptait à la fois les 5 modules
`chessable_to_pgn.*` (cible de la Phase 4b) et `chess_toolbox.bin.split_pgn.core`,
qui n'a aucun rapport avec ce chantier. Or `split_pgn.core` n'a lui-même
aujourd'hui aucun type hint, alors que son propre `CLAUDE.md`
(`src/chess_toolbox/bin/split_pgn/CLAUDE.md`) exige `@beartype`, mypy strict
et docstrings Google — typer les 5 modules `chessable_to_pgn.*` sans isoler
`split_pgn.core` aurait fait échouer `uv run inv lint` sur un module hors
périmètre.

**Décision :** scinder en deux blocs `[[tool.mypy.overrides]]` distincts.
Les 5 entrées `chessable_to_pgn.*` sont retirées de l'exemption (typage
réalisé, cf. Phase 4b) ; `split_pgn.core` reste seul dans un bloc dédié,
avec un commentaire signalant qu'il s'agit d'une dette pré-existante hors
périmètre, à traiter dans un chantier séparé si besoin.

**Conséquence :** `split_pgn.core` reste non typé et non couvert par mypy
strict — dette technique documentée mais non résorbée ici.
