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

## 2026-08-26 — Chantier 3 (couverture 80 %) : extension à `split_pgn`/`__main__`/`utils.py` plutôt que restriction du périmètre

Le spec initial de chantier 3 ne couvrait explicitement que les modules `chessable_to_pgn/*`, mais le seuil `fail_under = 80` de `[tool.coverage.report]` (`source = ["src/chess_toolbox"]`, sans `omit`) s'applique à tout `src/chess_toolbox`, y compris `split_pgn/core.py`, `__main__.py` et `utils.py` (non couverts par le spec). Sans les tester, le seuil global restait inatteignable quel que soit le niveau de couverture atteint sur le seul périmètre du spec.

**Décision (validée par l'utilisateur via question explicite) :** étendre le périmètre de chantier 3 à `split_pgn/core.py`, `__main__.py` et `utils.py`, plutôt que restreindre `fail_under`/ajouter un `omit` ou laisser le seuil échouer. Conséquence : nouveau bloc `[[tool.mypy.overrides]]` dédié à `tests.unit.test_split_pgn_core` (cf. `[[lesson]]` correspondante dans `LESSONS.md`) pour tester `split_pgn.core`, module legacy non typé, depuis un fichier de test strict.

**Résultat final :** 168 tests, couverture globale 84,11 % (seuil 80 % atteint). Fonctions Selenium (`_build_browser`, `loadHtmlFromWeb`, `start_automation_browser`, `login_and_save_cookies`, construction du navigateur dans `ChessableFetcher`) explicitement exclues du périmètre de test (nécessitent un navigateur réel). Restent non couvertes, en écart assumé une fois le seuil dépassé : `loadVariationInfo` (corps réel, toujours monkeypatché dans les tests de `processBatch`), le `break` de coupure à 500 chapitres dans `loadChapterInfo` (impraticable à déclencher), et la branche `args.chessable_args` de `__main__.py` (voir bug ci-dessous, non testée car code mort).

## 2026-08-26 — Bug signalé, non corrigé : branche `elif args.command == "extract-chessable"` morte dans `__main__.py`

`extract-chessable`, `chessable-start-browser` et `chessable-login` sont interceptés directement via `sys.argv` **avant** l'appel à `argparse.parse_args()`, chacun avec un `return` explicite (lignes ~36-55). La branche `elif args.command == "extract-chessable":` (lignes 172-187), placée après `parser.parse_args()`, est donc provablement inatteignable — et référence en plus `args.chessable_args`, un attribut jamais défini via `add_argument` sur ce sous-parseur.

**Décision :** signalé sans corriger (diff minimal, hors périmètre de chantier 3 qui est un chantier de tests, pas de correctif fonctionnel).

### 2026-08-26 — Ajout de `.pytest_cache/**` aux exclude_patterns d'okf-base.yaml plutôt que suppression manuelle ponctuelle du dossier

**Rationale :** Corrige la cause racine plutôt qu'un contournement à répéter à chaque session : sans ce pattern, tout commit échoue dès qu'un `pytest` local a été lancé avant, car okflint scanne le disque sans respecter .gitignore

## 2026-08-26 — Lot de finition post-chantier 3 : bug mort supprimé, `loadVariationInfo` couvert, dette mypy consignée

### Suppression de la branche morte `args.chessable_args` (`__main__.py`)

Signalée sans correction dans l'entrée précédente ("Bug signalé, non corrigé"). Sur relecture, aucune raison de la garder : du code mort identifié par la couverture n'apporte rien à laisser vivre, cela impose seulement de le re-diagnostiquer plus tard.

**Décision :** branche supprimée (lignes ~172-187). Aucune régression possible : `extract-chessable` reste intercepté avant `argparse` (lignes ~36-55, inchangées), et les tests `TestMain` de `test_main.py` couvrant cette sous-commande exercent tous ce chemin d'interception précoce, jamais l'ancienne branche morte. Confirmé par `pytest` (171 tests passent) et couverture de `__main__.py` à 99 % (seule la branche `if __name__ == "__main__":` elle-même reste non exercée, normal en test).

### `loadVariationInfo` : absence de couverture confirmée comme un oubli, corrigée

L'entrée "Chantier 3" ci-dessus qualifiait l'absence de couverture de `loadVariationInfo` d'« écart assumé ». Sur inspection du corps réel de la fonction et de sa chaîne d'appel (`WebFetch.getVariationDetailFromTag` → `WebFetch.getVariationHtml` → `WebFetch.getHtml`, cache-ou-réseau), seule la frontière `getVariationHtml` touche réellement Selenium ; le reste (construction du round `chapitre.variation`, filtrage des HTML absents, agrégation) est du parsing pur, sans dépendance réseau.

**Décision :** ajout de `TestLoadVariationInfo` dans `test_core.py`, qui appelle `loadVariationInfo` pour de vrai avec des tags de variation construits via `BeautifulSoup` (même style que les tests existants du fichier), en ne monkeypatchant que `WebFetch.getVariationHtml`. Couverture totale du projet passée de 84,11 % à 87,32 %. Seul le cutoff de sécurité à 5000 variations (lignes 213-216) reste non couvert, même rationale que le cutoff à 500 chapitres déjà accepté : impraticable à déclencher dans un test unitaire.

### `disallow_untyped_calls = false` sur `test_split_pgn_core.py` : dette assumée, pas neutre pour Phase 4b

L'objectif de la Phase 4b était de **supprimer** les exemptions mypy, pas d'en ajouter. L'override introduit pendant chantier 3 pour tester `split_pgn.core` (module legacy non typé) depuis un fichier de test strict va donc à l'encontre de cet objectif — même s'il est scopé au seul fichier de test, jamais au module de production (cf. `[[lesson]]` "mypy no-untyped-call..." dans `LESSONS.md` pour le détail technique).

**Décision :** consigné ici explicitement comme dette assumée, plutôt que de le laisser vivre comme une ligne de configuration parmi d'autres dans `pyproject.toml`.

**Condition de levée :** supprimable dès que `split_pgn/core.py` sort lui-même de son override `ignore_errors = true` (typage réel du module) — les erreurs `[no-untyped-call]` côté test disparaissent alors d'elles-mêmes, sans action supplémentaire.

## 2026-08-26 — Absorption de `chessable_to_pgn` comme code source ordinaire (fin du dépôt imbriqué)

`src/chess_toolbox/bin/chessable_to_pgn/` était un dépôt git imbriqué (son propre
`.git/`), sans `.gitmodules` au niveau du dépôt parent. Le parent l'enregistrait
donc comme un gitlink (mode 160000) sans URL associée — invisible depuis l'arbre
de travail local (les fichiers y sont physiquement présents), mais destructeur à
la première vraie utilisation : un clone frais aurait produit un répertoire
**vide** à cet emplacement (`git submodule update --init` est un no-op faute de
`.gitmodules`), et les deux workflows CI (`ci.yml`, `docs.yml`, tous deux en
`actions/checkout@v4` sans `submodules:`) n'auraient jamais récupéré le code. Voir la leçon correspondante
dans `LESSONS.md`.

**Décision :** absorber le sous-répertoire comme code source ordinaire du dépôt
parent plutôt que de régulariser un vrai submodule Git. Deux raisons :

1. Le code a divergé irréversiblement de l'upstream
   (`github.com/demastri/chessable-to-pgn`, John DeMastri, MIT) : renommage
   snake_case, typage complet, configuration pydantic, `WebFetch` réécrit. Une
   synchronisation upstream n'a plus de sens.
2. L'upstream n'accorde pas de droits de push — un submodule pointant dessus
   serait de toute façon impossible à faire évoluer normalement.

L'attribution MIT est conservée via `License.txt` et les docstrings des modules.
Un submodule Git réel aurait résolu le problème de clone, mais aurait imposé un
coût opérationnel permanent (init/update à chaque clone, gestion d'un second
remote) pour un bénéfice nul, l'upstream n'étant plus une cible de synchronisation.

**Mécanique :** `git rm --cached` du gitlink, suppression du `.git` imbriqué,
ré-ajout des fichiers comme blobs ordinaires (mode 100644). Historique complet
du dépôt imbriqué (5 refs : `master`, `multiproc`, et leurs suivis distants)
archivé avant suppression via `git bundle create --all`, vérifié
(`git bundle verify` + comparaison avec `git show-ref`) :
`C:/Users/matth/Documents/Dev/Python/archive/chessable-to-pgn-20260826.bundle`.

**Effet de bord traité dans la même passe :** les fichiers absorbés sont
désormais soumis aux hooks pre-commit du parent, qu'ils n'avaient jamais vus
(vague d'erreurs markdownlint sur `ReadMe.md` — titres setext convertis en ATX,
URL nue encadrée, frontmatter restauré après un bug de script de conversion —
corrigées, pas exclues). Le `CLAUDE.md` du sous-dossier (non chargé comme
mémoire projet par Claude Code depuis un sous-répertoire) a été fusionné dans le
`CLAUDE.md` racine (section « chessable_to_pgn — notes spécifiques » : setup
Selenium/Chrome for Testing, limitations connues) puis supprimé, pour éviter une
copie non chargée et vouée à devenir obsolète.

**Vérification bloquante avant push :** clone frais (`git clone --no-hardlinks
file:///...`), confirmant que `chessable_to_pgn/` n'est plus vide, puis dans ce
clone : `uv sync --all-extras`, 171 tests passants à 87,32 % de couverture,
`pre-commit run --all-files` sans erreur, build Sphinx réussi avec génération
effective de `docs/code/api/` (absent avant build) et zéro warning.

## 2026-08-26 — Correction de `docs.yml` : `uv sync --all-extras` + permissions Actions en écriture

Le premier push de l'absorption a révélé que le workflow CI « Build and deploy
Github pages » (`docs.yml`) échouait avec `sphinx-build: not found`, pour la
même raison déjà corrigée sur `ci.yml` le 2026-08-24 : `uv sync` (sans
`--all-extras`) n'installe pas les dépendances optionnelles, dont Sphinx.
[docs.yml:29](.github/workflows/docs.yml#L29) corrigé en conséquence.

Cette première correction a révélé un second problème, distinct et jusque-là
masqué par le premier : le job de déploiement échouait avec `403 Permission
denied to github-actions[bot]` en tentant de pousser la branche `gh-pages` —
le dépôt était configuré avec les permissions par défaut du `GITHUB_TOKEN` en
lecture seule (réglage historique de ce dépôt nouvellement créé sur GitHub).
Corrigé via `gh api --method PUT
repos/mattdav/chess_toolbox/actions/permissions/workflow -f
default_workflow_permissions=write`, avec l'accord explicite de l'utilisateur
(changement de sécurité au niveau du dépôt : accorde l'écriture à tous les
workflows du repo, pas seulement à `docs.yml`).

Après ces deux corrections, le workflow est passé au vert de bout en bout
(build Sphinx + push de `gh-pages`). Le site GitHub Pages public
(Settings → Pages → source `gh-pages`) n'a pas été activé — c'est une
décision de visibilité distincte, non demandée, laissée à l'utilisateur.
