---
type: Spec
id: SPEC-session-chessable
title: "Détection fiable de l'expiration de session Chessable"
description: "Détecter et signaler explicitement la perte de session avant d'écrire un résultat partiel ou vide"
status: implemented # draft | accepted | implemented | superseded
superseded-by:
work-item:
tags: [chessable, scraping, reliability]
timestamp: 2026-08-24
perimeter: project
audience: []
---

# Détection fiable de l'expiration de session Chessable

## Objectif

Quand la session Chessable est expirée, `bin/chessable_to_pgn` continue
aujourd'hui à s'exécuter sans échouer, jusqu'à produire un PGN vide ou partiel.
Le besoin est de détecter la perte de session au plus tôt et d'échouer de
façon explicite, plutôt que de laisser l'utilisateur découvrir après coup
qu'aucun chapitre n'a été extrait.

## Périmètre

### Inclus

- Détection de la redirection silencieuse de `/course/<id>` (ou
  `/variation/<id>`) vers la page d'accueil publique.
- Un mécanisme de preflight qui vérifie la session avant de traiter le moindre
  cours.
- Une exception dédiée qui interrompt le run sans écrire de fichier.

### Non-objectifs

Cette spec ne couvre pas l'automatisation de la reconnexion elle-même (au-delà
d'une option qui relance le navigateur d'authentification) : la saisie des
identifiants reste manuelle.

## Spécification fonctionnelle

Le comportement observé est le suivant : une requête sur `/course/<id>` avec
une session expirée DOIT normalement échouer, mais est en réalité redirigée
silencieusement vers la page d'accueil publique de Chessable. Le HTML renvoyé
est valide et volumineux (environ 150 Ko) mais ne contient aucun chapitre.

Le comportement attendu DOIT être : un échec rapide et explicite, sans
écriture de fichier (ni cache HTML ni PGN de sortie), dès que la session est
détectée comme invalide — que ce soit au preflight ou en cours de run.

## Choix et contraintes

Le signal primaire DOIT être la comparaison d'URL après navigation (la
redirection elle-même), indépendante de toute chaîne de caractères ou langue.
Les signaux de repli (marqueur authentifié, appel à l'action de connexion,
titre de page) ne sont utilisés qu'en complément.

## Critères d'acceptation

- [ ] Une session valide permet une extraction normale sans faux positif.
- [ ] Une session invalidée artificiellement produit un message explicite, un
      code de sortie non nul, et aucun fichier écrit.
- [ ] Un fichier HTML en cache reconnu comme page publique est ignoré et
      refetché, jamais rejoué (voir `FIX-cache-html-empoisonne`).
