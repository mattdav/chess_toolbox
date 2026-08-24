---
type: Fix
id: FIX-cache-html-empoisonne
title: "Cache HTML empoisonné par une page publique après expiration de session"
description: "Le cache HTML rejouait indéfiniment une page publique sans chapitre suite à une session expirée"
status: fixed # draft | confirmed | fixed | wontfix
severity: major # blocker | major | minor
work-item:
tags: [chessable, scraping, cache]
timestamp: 2026-08-24
perimeter: project
audience: []
---

# Cache HTML empoisonné par une page publique après expiration de session

## Symptôme

`chess_toolbox extract-chessable` se terminait avec « read 0 chapters » de
façon reproductible à l'identique, en un run d'environ 0,2 seconde — signe
qu'aucune requête réseau n'était réellement effectuée.

## Reproduction

Session Chessable expirée, cours déjà extrait au moins une fois avec succès
auparavant (donc un fichier HTML déjà présent en cache). Relancer
l'extraction en mode `update` (qui ne refetch jamais un fichier existant) :
le symptôme est immédiat et systématique.

## Comportement attendu

Voir `SPEC-session-chessable` : un fichier HTML en cache reconnu comme page
publique aurait dû être ignoré et refetché, jamais rejoué tel quel.

## Analyse

Cause racine : une requête sur `/course/<id>` avec une session expirée est
redirigée silencieusement vers la page d'accueil publique de Chessable
(HTML valide, ~150 Ko, aucun chapitre). Cette page a été mise en cache sans
validation de son contenu. Le mode d'exécution par défaut (`update`) ne
refetch jamais un fichier déjà présent sur disque — le mauvais HTML était
donc rejoué indéfiniment, sans qu'aucune nouvelle tentative réseau n'ait
lieu.

## Impact

Tous les cours dont le cache HTML avait été écrit pendant une fenêtre de
session expirée étaient affectés : extraction silencieusement vide ou
partielle jusqu'à purge manuelle du cache.

## Résolution

Correctif immédiat appliqué le 2026-08-24, avant le démarrage de ce chantier
de modernisation : garde-fou manuel à l'écriture et à la lecture du cache
HTML, réalignement du `.env` sur un profil Firefox valide, et
`CHESSABLE_HEADLESS` repassé à `false` (le mode headless favorisant la
détection par Cloudflare Bot Management, donc la redirection silencieuse).

Ce correctif est un garde-fou opérationnel, pas encore un mécanisme robuste
au niveau du code. La résolution durable — détection par comparaison d'URL,
preflight `ensure_session()`, exception `ChessableAuthError` dédiée — est
planifiée en Phase 4d de `PLAN-modernisation`, qui remplace le correctif
temporaire `_is_public_page` / `_warn_session_expired` actuellement présent
dans `web_fetch.py`.
