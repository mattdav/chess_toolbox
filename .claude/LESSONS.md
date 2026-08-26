---
type: ProjectJournal
project: chess_toolbox
updated: 2026-06-28
tags: [python, chess]
---

# Leçons apprises

## 2026-08-24 — Override mypy partiel : `disallow_untyped_defs` ≠ `disallow_incomplete_defs`

**Symptôme :** un `[[tool.mypy.overrides]]` ciblant un module legacy, avec
`disallow_untyped_defs = false`, ne supprime pas les erreurs
`no-untyped-def` ("Function is missing a return type annotation") sur des
fonctions *partiellement* annotées (paramètres typés, retour non typé).

**Fausse piste :** supposer un problème de résolution de module (nom qui ne
matche pas l'entrée de l'override) — vérifié via `mypy --verbose`
(`BuildSource(..., module=...)`), le nom correspondait exactement.

**Cause réelle :** `strict = true` active `disallow_incomplete_defs`
séparément de `disallow_untyped_defs`. Ce flag n'était pas désactivé par
l'override, et c'est lui (pas `disallow_untyped_defs`) qui gouverne le
message sur les fonctions partiellement typées. De même,
`check_untyped_defs = false` ne dispense de la vérification du corps que
pour les fonctions *totalement* non typées, pas les partiellement typées —
d'où des erreurs `[index]`/`[union-attr]` persistantes dans le corps de
fonctions déjà partiellement annotées.

**Fix :** pour une exemption complète d'un module legacy, utiliser
`ignore_errors = true` plutôt que d'énumérer des flags individuels — un flag
strict oublié suffit à laisser passer des erreurs en silence.

## 2026-08-25 — `-variations` isolées : cache toujours sous `course/one-off/`

**Symptôme :** en testant `-variations <id> -web all`, le fichier HTML
attendu sous `course/5193/variation/<id>.html` ne change ni de date de
modification ni de contenu après un run pourtant réussi (aucune erreur,
message "Processing variation ... Writing Course PGN file" affiché).

**Fausse piste :** en conclure que `-web all` (`FetchMode.FETCH_ALL`) n'était
plus correctement propagé après la réécriture argparse de la Phase 4c, ou
qu'un lock Firefox résiduel faisait échouer silencieusement le fetch.

**Cause réelle :** `processBatch` (`core.py`) fixe `courseId = "one-off"`
pour toute variation passée via `-variations`, quel que soit le cours réel
dont elle provient (comportement pré-existant, hors périmètre Phase 4c —
`core.py` n'a pas été touché). Le cache d'une variation isolée vit donc
toujours sous `course/one-off/variation/<id>.html`, jamais sous
`course/<vrai_id_cours>/variation/<id>.html`.

**Fix :** pour vérifier un fetch déclenché via `-variations`, contrôler
`course/one-off/variation/<id>.html`, pas le dossier du cours d'origine.

## 2026-08-25 — Phase 4c : comparatif des 3 modes de fenêtre (`WindowMode`)

Test sur les 24 variations du chapitre 0 du cours 5193 (via `-variations`,
`-web all` pour forcer un refetch réseau réel), un run par mode, mesuré avec
`time`. Échantillon de taille 1 par mode — variance réseau non isolée, à
prendre comme ordre de grandeur et non comme benchmark définitif.

| Mode        | Durée totale | Moy./variation | Résultat fonctionnel    |
| ----------- | -----------: | -------------: | ----------------------- |
| `offscreen` |     2 m 28 s |         ~6,2 s | 24/24 OK, aucune erreur |
| `headless`  |     3 m 19 s |         ~8,3 s | 24/24 OK, aucune erreur |
| `visible`   |     1 m 52 s |         ~4,7 s | 24/24 OK, aucune erreur |

Les 3 modes ont produit une extraction fonctionnelle complète (aucune
redirection vers la page publique, aucun message de session expirée) sur cet
échantillon. `headless` a été le plus lent des trois, cohérent avec le
risque documenté de longue date dans `.env` (Cloudflare Bot Management
détecte plus facilement Firefox headless, avec un risque de redirection
silencieuse vers la page d'accueil) — risque non observé ici, mais dont la
non-reproduction sur un seul run ne l'invalide pas. `offscreen` (nouveau
défaut) combine la même empreinte réseau que `visible` avec une fenêtre
invisible pour l'utilisateur, sans le désavantage `headless` : c'est le
compromis retenu comme défaut en Phase 4c.

Vérification "une seule fenêtre Firefox par run" faite par relecture de code
(`ChessableFetcher.__enter__`/`__exit__` dans `web_fetch.py`) plutôt que par
comptage de processus `firefox.exe` : Firefox est multi-processus par
architecture (process de contenu, GPU, etc.), donc un seul navigateur/une
seule fenêtre logique produit légitimement des dizaines de `firefox.exe`
dans le gestionnaire de tâches — ce compte n'est pas un signal fiable.

## 2026-08-25 — Phase 4d : `/dashboard/` ne redirige jamais, même sans session

**Symptôme :** `ensure_session()` (préflight comparant l'URL de
`/dashboard/` avant/après navigation, signal primaire imposé par
`SPEC-session-chessable`) ne levait jamais `ChessableAuthError`, même testé
avec un profil Firefox complètement vierge (sans aucun cookie). L'erreur
n'apparaissait finalement que plus tard, au premier fetch réel d'une
variation (`_assert_not_redirected` dans `loadHtmlFromWeb`) — le
comportement de bout en bout (message explicite, code de sortie 2, aucun
fichier écrit) restait correct, mais le préflight ne remplissait pas son
rôle de détection précoce avant tout traitement.

**Fausse piste :** supposer un bug dans `_assert_not_redirected` elle-même,
ou un délai d'attente insuffisant (`WebDriverWait` 15s + `sleep(2)`) avant
la comparaison d'URL.

**Cause réelle :** confirmé par un script de diagnostic isolé (navigation
répétée vers `/dashboard/` avec un profil vierge, lecture de
`browser.current_url` sur 10 secondes) : `/dashboard/` est une route
d'application cliente (SPA) qui reste affichée à la même URL que la session
soit valide ou non — aucune redirection serveur n'a lieu sur cette route
spécifique, contrairement aux pages de cours/variation qui redirigent bien
vers la racine du site.

**Fix :** utiliser `/profile/` comme URL de vérification dans
`ensure_session()` — confirmé par le même type de test qu'elle redirige
fidèlement vers la racine sans session, et reste sur `/profile/` avec une
session valide (testé sur le profil d'automatisation réel, déjà authentifié
depuis la Phase 4c). Leçon générale : pour un signal "comparaison d'URL
après navigation", valider empiriquement la route choisie avec un profil
sans session avant de la considérer fiable — certaines routes SPA ne
redirigent pas alors que d'autres pages du même site le font.

### 2026-08-25 — ensure_session() (préflight comparant l'URL de dashboard/ avant/après navigation) ne levait jamais ChessableAuthError, même testé avec un profil Firefox complètement vierge

**Mauvaise piste :** Supposer un bug dans _assert_not_redirected elle-même, ou un délai d'attente insuffisant avant la comparaison d'URL.

**Vraie cause :** dashboard/ est une route SPA qui reste affichée à la même URL que la session soit valide ou non — aucune redirection serveur n'a lieu sur cette route spécifique, contrairement aux pages de cours/variation qui redirigent bien vers la racine du site (confirmé par script de diagnostic isolé).

**Fix :** Utiliser profile/ comme URL de vérification — confirmé par le même type de test qu'elle redirige fidèlement sans session et reste stable avec une session valide. Pour tout signal 'comparaison d'URL après navigation', valider empiriquement la route choisie avec un profil sans session avant de la considérer fiable.

## 2026-08-26 — Doublons Sphinx sur les enums : napoleon traduit `Attributes:` en `.. attribute::`, en collision avec autodoc

**Symptôme :** `uv run inv docs` émettait "duplicate object description ... `<unknown>:1`" sur les trois enums du projet (`WindowMode`, `FetchMode`, `PgnMode`), sans que le message n'identifie clairement le fichier source en cause.

**Fausse piste :** chercher une directive `.. autoclass::` dupliquée dans le rst généré par `sphinx-apidoc`, ou une double exécution d'apidoc.

**Cause réelle :** une section Google `Attributes:` dans la docstring de classe d'un `enum.Enum` est traduite par napoleon en directives `.. attribute::`, une par membre — qui entrent en collision avec la documentation par membre qu'autodoc génère déjà lui-même depuis le rst d'apidoc.

**Fix :** retirer la section `Attributes:` et documenter chaque membre avec un commentaire `#:` juste au-dessus de sa ligne (voir `DECISIONS.md` pour le choix face à `napoleon_use_ivar`, qui masque le symptôme sans le corriger).

## 2026-08-26 — Doc GitHub Pages sans API : `sphinx-apidoc` n'était jamais appelé en CI

**Symptôme :** la documentation publiée sur GitHub Pages ne contenait que la page d'index, alors qu'un `uv run inv docs` local produit toutes les pages d'API sans erreur.

**Fausse piste :** aucune — le bug était silencieux (aucun message d'erreur, `sphinx-build` seul réussit très bien sans page d'API à générer).

**Cause réelle :** `.github/workflows/docs.yml` appelle uniquement `sphinx-build`, jamais `sphinx-apidoc` — `docs/code/api/` n'étant pas versionné (choix Phase 2), il est vide sur tout checkout CI propre. Seule l'invocation locale via `uv run inv docs` régénérait l'API au préalable. Même classe de bug déjà observée sur `chess_coach` (projet sœur, même template).

**Fix :** générer l'API depuis `docs/code/conf.py` (hook `builder-inited`) plutôt que dans une étape CI séparée, pour que toute invocation de `sphinx-build` — locale ou CI — la déclenche automatiquement. Ajouter `-W --keep-going` au `sphinx-build` de la CI pour qu'un futur défaut similaire fasse échouer le job au lieu de publier une doc incomplète.
