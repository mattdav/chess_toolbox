# CLAUDE.md — split_pgn

Ce fichier guide Claude Code pour les travaux sur le sous-outil `split_pgn`.

## Ce que fait split_pgn

`split_pgn` découpe un fichier PGN contenant un arbre d'ouvertures en fichiers PGN séparés, un par variante/défense. Il est conçu pour être utilisé avec ChessBase.

Fonctionnalités :
- Navigation dans l'arbre PGN à partir d'une séquence de coups donnée (SAN ou UCI)
- Découpe à une profondeur configurable
- Préservation des commentaires, annotations (NAG) et sous-variantes
- Inclusion du FEN de départ dans chaque fichier généré (compatibilité ChessBase)
- Mode `--list` pour afficher les variantes disponibles sans créer de fichiers

## Commandes

```bash
# Via la CLI unifiée
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --list
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --depth 2 --output sicilienne/

# En direct (développement)
uv run python -m chess_toolbox.bin.split_pgn core.py repertoire.pgn --moves "1.e4"
```

## Architecture

```
split_pgn/
├── CLAUDE.md       # Ce fichier
├── __init__.py     # Expose main() et les fonctions publiques clés
└── core.py         # Logique métier complète
```

### Fonctions publiques dans `core.py`

| Fonction | Rôle |
|---|---|
| `parse_pgn_file(path)` | Lit un fichier PGN et retourne le premier jeu |
| `san_to_uci_sequence(san_string)` | Convertit une séquence SAN en liste UCI |
| `follow_moves(game, uci_moves)` | Navigue dans l'arbre jusqu'à la position cible |
| `copy_subtree(src_node, dst_node, board)` | Copie récursive d'un sous-arbre |
| `node_to_pgn_string(node, board, headers, label)` | Sérialise un nœud en PGN avec FEN |
| `list_variations(node, board, depth)` | Liste les variantes disponibles |
| `extract_branches(node, board, headers, output_dir, depth)` | Découpe et écrit les fichiers |
| `main(args)` | Point d'entrée CLI (reçoit un `argparse.Namespace`) |

### Pipeline d'exécution

```
parse_pgn_file()
    → san_to_uci_sequence()   # convertit "--moves" en liste UCI
    → follow_moves()           # navigue jusqu'à la position de départ
    → list_variations()        # si --list
    → extract_branches()       # sinon : découpe et écrit
        → node_to_pgn_string() # pour chaque variante
            → copy_subtree()   # copie récursive du sous-arbre
```

## Points d'attention

### Compatibilité ChessBase
Le FEN de départ est inséré dans les headers du PGN via `new_game.setup(board_at_node)`. Ceci est essentiel pour que ChessBase accepte les fichiers. Ne pas retirer cette ligne.

### Gestion des coups illisibles
`san_to_uci_sequence()` essaie d'abord de parser le token comme UCI, puis comme SAN. En cas d'échec, il lève `ValueError` avec un message clair.

### Nommage des fichiers de sortie
`safe_filename()` remplace les espaces par `_` et supprime les caractères non-alphanumériques pour garantir la compatibilité multi-OS. Le résultat peut différer du label SAN (ex: `1.e4_c5_Sicilienne.pgn`).

## Configuration (depuis config.yaml)

```yaml
split_pgn:
  default_depth: 1           # Profondeur de découpe par défaut
  default_output_suffix: "_split"  # Suffixe du dossier de sortie par défaut
```

Aucune variable secrète dans `.env` — ce module ne fait pas d'appels réseau.

## Standards de qualité

- `@beartype` sur toutes les fonctions publiques
- Mypy strict : 0 erreur
- Docstrings Google style sur toutes les fonctions publiques
- Tests unitaires pour :
  - `san_to_uci_sequence` (cas normaux, SAN avec numéros, UCI, coups illisibles)
  - `follow_moves` (séquence valide, séquence introuvable)
  - `safe_filename` (cas limites : chaîne vide, caractères spéciaux)
  - `list_variations` (depth 1, depth 2)

## Exemples typiques

```bash
# Lister les défenses après 1.e4
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --list

# Découper par défense (1 fichier par réponse noire)
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4"

# Découper en 2 niveaux
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --depth 2

# Travailler depuis la Sicilienne
uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4 c5" --list --depth 2
```
