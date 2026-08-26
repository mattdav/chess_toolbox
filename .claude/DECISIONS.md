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

## 2026-08-25 — Phase 4c : `ChessableFetcher` + `WindowMode.OFFSCREEN` plutôt que headless seul

`core.py` reste explicitement hors périmètre Phase 4c (il ne fait qu'appeler
`command_line.processCommandLineParams()` et l'API `WebFetch`/`Pgn`, dont
aucune signature externe n'a changé). Un seul navigateur par run est donc
obtenu en encapsulant le cycle de vie Firefox dans un gestionnaire de
contexte (`ChessableFetcher`, ajouté à `web_fetch.py`) plutôt qu'en modifiant
`core.py` : `WebFetch.browser` (nouveau `ClassVar`, même pattern que
`doFetch`) est construit une fois dans `ChessableFetcher.__enter__` et
réutilisé par `loadHtmlFromWeb` pour tous les fetches (y compris les 3
tentatives de retry, qui ne reconstruisaient auparavant plus le navigateur à
chaque essai). Les deux points d'appel de `chessable_main()` dans
`src/chess_toolbox/__main__.py` sont enveloppés dans
`with ChessableFetcher():`.

`CHESSABLE_WINDOW_MODE` (enum `WindowMode` dans `config/settings.py`,
remplace `CHESSABLE_HEADLESS`) introduit un troisième mode `offscreen`, en
plus de `headless`/`visible` : une fenêtre Firefox réelle (pas
`--headless`), déplacée hors de tout écran via
`browser.set_window_position(-32000, -32000)` après construction. Choisi
comme défaut car il conserve la même empreinte réseau/rendu que `visible`
(donc la même résistance à la détection Cloudflare Bot Management, cf. note
historique dans `.env` sur le risque de redirection silencieuse en mode
headless — voir aussi `[[lesson]]` correspondante dans `LESSONS.md`) tout en
restant invisible pour l'utilisateur, contrairement à `headless` qui cumule
les deux inconvénients (rendu différent + toujours une fenêtre invisible).

**Réécriture `command_line.py` en `argparse`** : flags legacy à un tiret
conservés à l'identique (choix utilisateur explicite), via
`parser.parse_known_args()` pour préserver le comportement "avertir et
continuer" sur un token inconnu (pas de `SystemExit`). Point non couvert par
défaut par `argparse` : un flag à valeur (ex. `-web`) sans token suivant lève
normalement `SystemExit(2)` (comportement différent de l'ancien parsing
manuel, qui retournait proprement `(None, None, None)`). Corrigé via
`exit_on_error=False` sur le constructeur `ArgumentParser` +
`try/except argparse.ArgumentError` autour de `parse_known_args()`, détecté
par relecture indépendante du code du sous-agent (pas par ses propres tests)
puis confirmé par reproduction directe (`sys.argv=['prog','-web']` levait
`SystemExit 2` avant fix, retourne `(None, None, None)` après).

**Conséquence :** `-variations` isolées utilisent toujours `courseId =
"one-off"` comme placeholder de cache (comportement pré-existant de
`core.py`, non modifié) — void `[[lesson]]` "cache toujours sous
`course/one-off/`" dans `LESSONS.md` pour le piège associé, découvert lors
du test comparatif des 3 modes.

## 2026-08-25 — Phase 4d : `_is_public_page` conservé (narrowé), `profile/` plutôt que `dashboard/` pour `ensure_session()`

Le plan demandait littéralement la « suppression de `_is_public_page` /
`_warn_session_expired` », mais `SPEC-session-chessable` exige par ailleurs
qu'un cache HTML déjà sur disque reconnu comme page publique soit toujours
ignoré et refetché (`FIX-cache-html-empoisonne`) — cas où aucune navigation
live n'a lieu, donc aucune comparaison d'URL n'est possible.

**Décision :** `_is_public_page`/`PUBLIC_PAGE_TITLE` sont conservés mais
narrowés au seul chemin de lecture de cache sur disque
(`getHtml`/`FetchMode.FETCH_NONE`/`FETCH_UPDATE` avec fichier existant).
`_warn_session_expired` (print-et-continuer sur un fetch réseau live) est
supprimé et remplacé par `ChessableAuthError`, levée par
`_assert_not_redirected` (comparaison d'URL, signal primaire imposé par la
spec) — appelée à la fois par `ensure_session()` (préflight) et par
`loadHtmlFromWeb()` (par requête, retry loop exempté via
`except ChessableAuthError: raise`).

**`ensure_session()` navigue vers `profile/`, pas `dashboard/`** : testé
empiriquement avec un profil Firefox vierge (sans cookies) — `dashboard/`
est une route SPA qui ne redirige jamais côté serveur même sans session
(URL inchangée après navigation + attente), rendant la comparaison d'URL
inopérante sur cette page. `profile/` redirige fidèlement vers la racine du
site sans session, et reste sur `profile/` avec une session valide (vérifié
sur le profil d'automatisation réel, déjà authentifié depuis la Phase 4c) —
voir `[[lesson]]` correspondante dans `LESSONS.md`.

**`ChessableFetcher.__enter__`** appelle `ensure_session()` juste après la
construction du navigateur ; si elle lève, le navigateur est explicitement
fermé avant de relever l'exception (`__exit__` n'est jamais invoqué quand
`__enter__` lève lui-même).

**`--relogin`** : détecté et retiré de `sys.argv` dans le même bloc
d'interception précoce que `extract-chessable` (avant argparse), appelle
`login_and_save_cookies()` puis poursuit l'extraction normalement.

**Vérifié en conditions réelles** (pas seulement par relecture) :
session invalide (profil Firefox vierge) → `ChessableAuthError` levée au
préflight, message explicite, code de sortie 2, aucun fichier HTML écrit ;
session valide (profil d'automatisation réel) → extraction normale
inchangée, code de sortie 0.

### 2026-08-25 — Dans web_fetch.py,_is_public_page/PUBLIC_PAGE_TITLE sont conservés (pas supprimés comme le texte littéral du plan le suggérait) mais narrowés au seul chemin de lecture d'un cache HTML déjà sur disque ; _warn_session_expired (print-et-continuer sur fetch réseau live) est supprimé et remplacé par ChessableAuthError

**Rationale :** SPEC-session-chessable exige que le cache HTML déjà sur disque reconnu comme page publique soit toujours ignoré et refetché (FIX-cache-html-empoisonne) — cas où aucune navigation live n'a lieu, donc aucune comparaison d'URL n'est possible. Supprimer entièrement _is_public_page aurait rendu ce critère d'acceptation impossible à satisfaire.

### 2026-08-25 — ensure_session() navigue vers profile/ plutôt que dashboard/ pour vérifier la validité de la session

**Rationale :** Testé empiriquement avec un profil Firefox vierge (sans cookies) : dashboard/ est une route SPA qui ne redirige jamais côté serveur même sans session, rendant la comparaison d'URL inopérante. profile/ redirige fidèlement vers la racine sans session, et reste stable avec une session valide.

### 2026-08-25 — --relogin est intercepté et retiré de sys.argv dans le même bloc d'interception précoce que extract-chessable (avant argparse), avant d'appeler login_and_save_cookies()

**Rationale :** Cohérent avec l'interception déjà en place pour extract-chessable/chessable-start-browser/chessable-login (arguments legacy à un tiret incompatibles avec argparse).

### 2026-08-26 — Documentation des membres d'enum via commentaires `#:` plutôt que `napoleon_use_ivar = True`

**Rationale :** `napoleon_use_ivar = True` supprime l'avertissement de doublon napoleon/autodoc mais au prix de ne plus jamais afficher la description des membres dans le rendu HTML — il masque le symptôme sans documenter l'enum. Les commentaires `#:` (attribute docs Sphinx natifs, lus directement par autodoc) restent visibles dans le rendu et n'entrent pas en conflit avec la documentation par membre générée depuis le rst d'apidoc. Appliqué à `WindowMode`, `FetchMode`, `PgnMode`.

### 2026-08-26 — Génération de l'API (`sphinx-apidoc`) déplacée dans `docs/code/conf.py` plutôt qu'ajoutée comme étape CI

**Rationale :** `.github/workflows/docs.yml` n'appelait jamais `sphinx-apidoc`, seulement `sphinx-build` — en CI, `docs/code/api/` (non versionné) restait donc vide et seule la page d'index était publiée sur GitHub Pages. Ajouter un step `sphinx-apidoc` dans le workflow aurait dupliqué la commande (déjà présente dans `inv docs`) avec un risque de divergence des options entre les deux. La génération est donc déclenchée depuis `conf.py` via le hook `builder-inited` (`setup(app)`), source unique de vérité pour local et CI ; le step `sphinx-apidoc` de `tasks.py` devient redondant et est retiré.
