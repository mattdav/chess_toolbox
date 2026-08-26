"""Point d'entrée CLI unifié de chess_toolbox.

Sous-commandes disponibles :
    split-pgn           Découpe un PGN d'ouvertures en fichiers par variante
    extract-chessable   Exporte un cours Chessable au format PGN

Exemples :
    uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --depth 2
    uv run chess_toolbox extract-chessable -courses 12345
    uv run chess_toolbox extract-chessable -interactive
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    """Charge le fichier .env depuis le répertoire de travail courant.

    Quand on lance `uv run chess_toolbox` depuis la racine du projet,
    Path.cwd() est le répertoire qui contient le .env.
    """
    load_dotenv(Path.cwd() / ".env")


def main() -> None:
    """Dispatcher principal du CLI chess_toolbox."""
    _load_env()

    # extract-chessable est intercepté AVANT argparse : les arguments du moteur
    # chessable-to-pgn utilisent le style legacy à un tiret (-courses, -variations…)
    # qui entre en conflit avec le parsing argparse des arguments optionnels.
    if len(sys.argv) > 1 and sys.argv[1] == "extract-chessable":
        from chess_toolbox.bin.chessable_to_pgn import main as chessable_main
        from chess_toolbox.bin.chessable_to_pgn.web_fetch import (
            ChessableAuthError,
            ChessableFetcher,
            login_and_save_cookies,
        )

        engine_args = sys.argv[2:]
        if "--relogin" in engine_args:
            engine_args = [a for a in engine_args if a != "--relogin"]
            login_and_save_cookies()
        sys.argv = [sys.argv[0]] + engine_args
        try:
            with ChessableFetcher():
                chessable_main()
        except ChessableAuthError as e:
            print(str(e))
            sys.exit(2)
        return

    # chessable-start-browser : lance Chrome normal avec le port de debug CDP.
    # Approche recommandée pour contourner Cloudflare Bot Management.
    if len(sys.argv) > 1 and sys.argv[1] == "chessable-start-browser":
        from chess_toolbox.bin.chessable_to_pgn.web_fetch import (
            start_automation_browser,
        )

        start_automation_browser()
        return

    # chessable-login : ouvre CfT, attend la connexion manuelle, sauvegarde les cookies.
    if len(sys.argv) > 1 and sys.argv[1] == "chessable-login":
        from chess_toolbox.bin.chessable_to_pgn.web_fetch import login_and_save_cookies

        profile = sys.argv[2] if len(sys.argv) > 2 else "Default"
        login_and_save_cookies(profile)
        return

    parser = argparse.ArgumentParser(
        prog="chess_toolbox",
        description="Boîte à outils d'administration PGN pour les échecs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --list
  uv run chess_toolbox split-pgn repertoire.pgn --moves "1.e4" --depth 2
  uv run chess_toolbox extract-chessable -courses 12345
  uv run chess_toolbox extract-chessable -variations 67890
  uv run chess_toolbox extract-chessable -interactive
        """,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMANDE")
    subparsers.required = True

    # ── split-pgn ──────────────────────────────────────────────────────────
    split_parser = subparsers.add_parser(
        "split-pgn",
        help="Découpe un PGN d'ouvertures en fichiers par variante.",
        description="Découpe un PGN d'ouvertures en fichiers par variante.",
    )
    split_parser.add_argument("pgn_file", help="Fichier PGN source")
    split_parser.add_argument(
        "--moves",
        default="",
        help="Position de départ en SAN ou UCI. Ex: '1.e4 c5'",
    )
    split_parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Profondeur de découpe après la position (défaut: 1)",
    )
    split_parser.add_argument(
        "--output",
        default="",
        help="Dossier de sortie (défaut: <nom_pgn>_split/)",
    )
    split_parser.add_argument(
        "--list",
        action="store_true",
        help="Lister les variantes disponibles sans créer de fichiers",
    )

    # ── extract-chessable ──────────────────────────────────────────────────
    subparsers.add_parser(
        "extract-chessable",
        help="Exporte un cours Chessable au format PGN.",
        description=(
            "Exporte les cours Chessable au format PGN. "
            "Tous les arguments sont transmis directement au moteur chessable-to-pgn."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Arguments transmis au moteur :
  -courses ID [ID ...]    Identifiants de cours à exporter
  -variations ID [ID ...] Identifiants de variantes individuelles
  -interactive            Mode interactif
  -web update|all|none    Stratégie de récupération HTML
  -pgn none|incremental|after   Mode d'écriture PGN
  -pgnroot CHEMIN         Dossier de sortie des PGN
  -htmlroot CHEMIN        Dossier de cache HTML
  -browserbinary CHEMIN   Chemin vers l'exécutable Chrome
  -browserprofiledir CHEMIN  Répertoire profils Chrome
  -browserprofile NOM     Nom du profil Chrome

Option locale (non transmise au moteur) :
  --relogin               Relance la connexion manuelle Chessable avant
                           l'extraction (session expirée ou absente)

Variables d'environnement (.env) :
  CHROME_BINARY_PATH      Chemin vers Chrome (prioritaire sur -browserbinary)
  CHROME_PROFILE_DIR      Répertoire profils Chrome
  CHROME_PROFILE          Nom du profil (défaut: Default)
  CHESSABLE_HTML_CACHE    Dossier de cache HTML (défaut: ./html/)
  CHESSABLE_PGN_CACHE     Dossier de sortie PGN (défaut: ./pgn/)
        """,
    )
    args = parser.parse_args()

    if args.command == "split-pgn":
        from chess_toolbox.bin.split_pgn import main as split_main

        # Reconstruit la liste d'arguments pour split_pgn.main(argv)
        argv = [args.pgn_file]
        if args.moves:
            argv += ["--moves", args.moves]
        if args.depth != 1:
            argv += ["--depth", str(args.depth)]
        if args.output:
            argv += ["--output", args.output]
        if args.list:
            argv.append("--list")
        split_main(argv)


if __name__ == "__main__":
    main()
