# Journal

Journal du projet. Chaque entrée est un titre de niveau 2 au format
`## AAAA-MM-JJ` (fichier réservé OKF, cf. `okf-base.yaml`).

## 2026-08-24

- Correctif opérationnel de l'incident cache HTML empoisonné (garde-fou
  manuel, `.env` réaligné, `CHESSABLE_HEADLESS=false`) — voir
  `docs/fixes/FIX-cache-html-empoisonne.md`.
- Démarrage du chantier de modernisation `chess_toolbox`, cadré par
  `docs/specs/SPEC-alignement-template.md` et
  `docs/specs/SPEC-session-chessable.md`, suivi dans
  `docs/plans/PLAN-modernisation.md`.
- Phase 0 (rattachement cruft), Phase 1 (scaffolding qualité) et Phase 2
  (documentation et conformité OKF) du plan réalisées.
