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
