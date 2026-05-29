#!/usr/bin/env python3
"""
split_pgn.py - Découpe un fichier PGN d'arbre d'ouvertures en fichiers séparés
par défense/variante à partir d'une position de départ donnée.

Tous les commentaires, annotations (NAG) et sous-variantes sont préservés.
Le FEN de départ est intégré dans chaque fichier généré, ce qui permet de
les réimporter directement dans ChessBase ou tout autre logiciel.

Usage:
    python split_pgn.py <fichier.pgn> --moves "1.e4" --list
    python split_pgn.py <fichier.pgn> --moves "1.e4"
    python split_pgn.py <fichier.pgn> --moves "1.e4" --depth 2
    python split_pgn.py <fichier.pgn> --moves "1.e4 c5"
    python split_pgn.py <fichier.pgn> --moves "1.e4 c5" --list --depth 2
"""

import argparse
import io
import os
import re
import sys

import chess
import chess.pgn

# ─────────────────────────────────────────────
# Chargement
# ─────────────────────────────────────────────


def parse_pgn_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        game = chess.pgn.read_game(f)
    if game is None:
        raise ValueError(f"Impossible de lire un jeu PGN dans {path}")
    return game


# ─────────────────────────────────────────────
# Conversion SAN / UCI
# ─────────────────────────────────────────────


def san_to_uci_sequence(san_string):
    board = chess.Board()
    uci_moves = []
    tokens = re.split(r"\s+", san_string.strip())
    cleaned = []
    for t in tokens:
        if not t:
            continue
        m = re.match(r"^\d+\.+(.+)$", t)
        if m:
            cleaned.append(m.group(1))
        elif re.match(r"^\d+\.+$", t):
            continue
        else:
            cleaned.append(t)
    for token in cleaned:
        if not token:
            continue
        try:
            move = chess.Move.from_uci(token)
            if move in board.legal_moves:
                board.push(move)
                uci_moves.append(token)
                continue
        except Exception:
            pass
        try:
            move = board.parse_san(token)
            uci_moves.append(move.uci())
            board.push(move)
        except Exception as e:
            raise ValueError(f"Coup illisible : '{token}' ({e})") from e
    return uci_moves


# ─────────────────────────────────────────────
# Navigation dans l'arbre
# ─────────────────────────────────────────────


def follow_moves(game, uci_moves):
    """Retourne (node, board) après avoir suivi uci_moves dans l'arbre."""
    node = game
    board = game.board()
    for uci in uci_moves:
        move = chess.Move.from_uci(uci)
        found = None
        for var in node.variations:
            if var.move == move:
                found = var
                break
        if found is None:
            return None, board
        node = found
        board.push(move)
    return node, board


# ─────────────────────────────────────────────
# Copie du sous-arbre
# ─────────────────────────────────────────────


def copy_subtree(src_node, dst_node, current_board):
    """
    Copie récursivement les variations de src_node dans dst_node.
    current_board est le board APRÈS le coup de src_node.
    """
    for var in src_node.variations:
        move = var.move
        if move not in current_board.legal_moves:
            continue
        child = dst_node.add_variation(
            move,
            comment=var.comment,
            starting_comment=var.starting_comment,
            nags=list(var.nags),
        )
        sub_board = current_board.copy()
        sub_board.push(move)
        copy_subtree(var, child, sub_board)


# ─────────────────────────────────────────────
# Création d'un jeu depuis un nœud
# ─────────────────────────────────────────────


def node_to_pgn_string(node, board_at_node, headers, label):
    """
    Crée un PGN à partir d'un nœud.
    - node           : le nœud de départ (son coup est le 1er du nouveau jeu)
    - board_at_node  : le board APRÈS le coup de ce nœud
    - headers        : headers originaux
    - label          : label pour White/Black

    Le FEN de départ (position avant le coup du nœud) est inclus dans les headers,
    ce qui garantit la compatibilité ChessBase.
    """
    # Position avant le coup de ce nœud = parent
    # On recule d'un coup sur le board pour obtenir le FEN de départ
    # board_at_node est APRÈS le coup du nœud, donc on a déjà poussé le coup.
    # On utilise directement board_at_node comme position de départ.

    new_game = chess.pgn.Game()

    # Copier les headers originaux
    for k, v in headers.items():
        new_game.headers[k] = v
    new_game.headers["White"] = label
    new_game.headers["Black"] = label
    new_game.headers["Result"] = "*"

    # Définir le FEN de départ = board_at_node (position APRÈS le coup du nœud)
    # Les coups suivants dans le fichier correspondent aux continuations
    new_game.setup(board_at_node)

    # Commentaire éventuel du nœud de départ
    if node.comment:
        new_game.comment = node.comment

    # Copier toutes les sous-variantes
    copy_subtree(node, new_game, board_at_node.copy())

    # Sérialiser
    output = io.StringIO()
    print(new_game, file=output)
    return output.getvalue()


# ─────────────────────────────────────────────
# Listing
# ─────────────────────────────────────────────


def list_variations(node, board, depth=1, current_depth=0, prefix=""):
    results = []
    if current_depth >= depth:
        return results
    for var in node.variations:
        move = var.move
        if move not in board.legal_moves:
            continue
        san = board.san(move)
        mn = board.fullmove_number
        td = "." if board.turn == chess.WHITE else "..."
        label = f"{prefix} {mn}{td}{san}".strip() if prefix else f"{mn}{td}{san}"
        results.append(label)
        sub = board.copy()
        sub.push(move)
        results.extend(list_variations(var, sub, depth, current_depth + 1, label))
    return results


# ─────────────────────────────────────────────
# Extraction et écriture
# ─────────────────────────────────────────────


def safe_filename(label):
    s = label.replace(" ", "_")
    s = re.sub(r"[^\w\-]", "", s)
    return s or "variante"


def extract_branches(
    node, board, headers, output_dir, depth=1, current_depth=0, path_san=""
):
    if current_depth >= depth:
        return 0
    count = 0
    for var in node.variations:
        move = var.move
        if move not in board.legal_moves:
            continue
        san = board.san(move)
        mn = board.fullmove_number
        td = "." if board.turn == chess.WHITE else "..."
        full_label = (
            f"{path_san} {mn}{td}{san}".strip() if path_san else f"{mn}{td}{san}"
        )

        sub_board = board.copy()
        sub_board.push(move)

        if current_depth == depth - 1:
            pgn_str = node_to_pgn_string(var, sub_board, headers, full_label)
            fname = safe_filename(full_label) + ".pgn"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(pgn_str)
            print(f"  ✓  {full_label:45s}  →  {fname}")
            count += 1
        else:
            count += extract_branches(
                var,
                sub_board,
                headers,
                output_dir,
                depth,
                current_depth + 1,
                full_label,
            )
    return count


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Découpe un PGN d'arbre d'ouvertures en fichiers par variante.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Lister les défenses après 1.e4
  python split_pgn.py repertoire.pgn --moves "1.e4" --list

  # Découper par défense (1 fichier par réponse noire)
  python split_pgn.py repertoire.pgn --moves "1.e4"

  # Découper en 2 niveaux (défense + 2e coup blanc)
  python split_pgn.py repertoire.pgn --moves "1.e4" --depth 2

  # Travailler depuis la Sicilienne uniquement
  python split_pgn.py repertoire.pgn --moves "1.e4 c5"
  python split_pgn.py repertoire.pgn --moves "1.e4 c5" --list --depth 2

  # Spécifier le dossier de sortie
  python split_pgn.py repertoire.pgn --moves "1.e4" --output mes_defenses/
        """,
    )
    parser.add_argument("pgn_file", help="Fichier PGN source")
    parser.add_argument(
        "--moves", default="", help="Position de départ en SAN ou UCI. Ex: '1.e4 c5'"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Profondeur de découpe après la position (défaut: 1)",
    )
    parser.add_argument(
        "--output", default="", help="Dossier de sortie (défaut: <nom_pgn>_split/)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lister les variantes disponibles sans créer de fichiers",
    )
    args = parser.parse_args(argv)

    print(f"\n📖  Lecture : {args.pgn_file}")
    game = parse_pgn_file(args.pgn_file)
    headers = dict(game.headers)
    print(f"    Partie  : {headers.get('White', '?')} vs {headers.get('Black', '?')}")

    if args.moves.strip():
        try:
            uci_seq = san_to_uci_sequence(args.moves)
        except ValueError as e:
            print(f"\n❌  {e}")
            sys.exit(1)

        start_node, start_board = follow_moves(game, uci_seq)
        if start_node is None:
            print(f"\n❌  Séquence introuvable dans l'arbre : '{args.moves}'")
            print("    Utilisez --list pour voir les variantes disponibles.")
            sys.exit(1)

        board_tmp = game.board()
        san_parts = []
        for uci in uci_seq:
            mv = chess.Move.from_uci(uci)
            mn = board_tmp.fullmove_number
            td = "." if board_tmp.turn == chess.WHITE else "..."
            san_parts.append(f"{mn}{td}{board_tmp.san(mv)}")
            board_tmp.push(mv)
        start_label = " ".join(san_parts)
        print(f"    Départ  : {start_label}")
    else:
        start_node = game
        start_board = game.board()
        start_label = "(position initiale)"
        print(f"    Départ  : {start_label}")

    nb = len(start_node.variations)
    print(f"    Variantes disponibles : {nb}\n")

    if nb == 0:
        print("⚠️   Aucune variante à cette position.")
        sys.exit(0)

    if args.list:
        print(f"📋  Variantes (profondeur {args.depth}) :\n")
        for v in list_variations(start_node, start_board, depth=args.depth):
            print(f"    • {v}")
        return

    base = os.path.splitext(os.path.basename(args.pgn_file))[0]
    output_dir = args.output if args.output else f"{base}_split"
    os.makedirs(output_dir, exist_ok=True)
    print(f"✂️   Découpe (profondeur {args.depth}) → {output_dir}/\n")
    count = extract_branches(
        start_node, start_board, headers, output_dir, depth=args.depth
    )
    print(f"\n✅  {count} fichier(s) créé(s) dans '{output_dir}/'")


if __name__ == "__main__":
    main()
