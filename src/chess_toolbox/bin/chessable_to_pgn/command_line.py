#!/usr/bin/env python3
"""Outils d'extraction des paramètres de ligne de commande.

Définit les modes de traitement de l'application et fournit les commandes
du mode interactif.

Portage du projet chessable-to-pgn de John DeMastri (MIT), v0.3,
chess@demastri.com.
"""

import argparse
import sys
from pathlib import Path

from beartype import beartype

from chess_toolbox.config.settings import settings

from . import utilities
from .pgn_writer import Pgn, PgnMode
from .web_fetch import FetchMode, WebFetch


def _build_parser() -> argparse.ArgumentParser:
    """Construit le parser des arguments legacy à un tiret de chessable-to-pgn.

    ``add_help=False`` : l'ancien parsing manuel ne gérait pas ``-h``/``--help``
    (un tel argument tombait dans le message générique "Don't know how to
    apply..."), ce comportement est préservé à l'identique.

    Returns:
        Parser configuré avec l'ensemble des flags à un tiret existants.
    """
    # exit_on_error=False : un flag comme -web sans valeur suivante doit rester
    # gérable comme un argument invalide ordinaire (l'ancien parsing manuel
    # retournait proprement (None, None, None)), pas déclencher un SystemExit.
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("-courses", nargs="*", default=[])
    parser.add_argument("-variations", nargs="*", default=[])
    parser.add_argument(
        "-interactive", dest="processMode", action="store_const", const="interactive"
    )
    parser.add_argument(
        "-batch", dest="processMode", action="store_const", const="batch"
    )
    parser.add_argument("-web", default=None)
    parser.add_argument("-key", action="store_true", default=False)
    parser.add_argument("-nokey", action="store_true", default=False)
    parser.add_argument("-pgn", default=None)
    parser.add_argument("-pgnroot", default=None)
    parser.add_argument("-htmlroot", default=None)
    parser.add_argument("-browserbinary", default=None)
    parser.add_argument("-browserprofiledir", default=None)
    parser.add_argument("-browserprofile", default=None)
    return parser


def _split_integer_tokens(tokens: list[str]) -> tuple[list[str], list[str]]:
    """Sépare des tokens bruts entre identifiants entiers et le reste.

    Reproduit le filtrage ``argIsInt`` de l'ancien parsing manuel : seuls les
    tokens numériques capturés après ``-courses``/``-variations`` sont
    retenus, les autres sont signalés comme arguments inconnus.

    Args:
        tokens: Tokens bruts capturés après le flag.

    Returns:
        Tuple ``(identifiants entiers valides, tokens rejetés)``.
    """
    valid = [t for t in tokens if utilities.is_integer(t)]
    invalid = [t for t in tokens if not utilities.is_integer(t)]
    return valid, invalid


@beartype
def processCommandLineParams() -> tuple[str | None, list[str] | None, list[str] | None]:
    """Parse ``sys.argv`` et positionne les modes globaux ``WebFetch``/``Pgn``.

    Utilise ``argparse`` (``parse_known_args``) pour reproduire le
    comportement de l'ancien parsing manuel token par token : les flags à un
    seul tiret sont préservés à l'identique, et un argument inconnu affiche
    un avertissement au lieu de faire échouer le programme (pas de
    ``SystemExit``).

    Returns:
        Tuple ``(mode de traitement, liste des cours, liste des variations)``.
        Retourne ``(None, None, None)`` si un argument est invalide.
    """
    # there really just end up being three functional  parameters
    # - web  - All (overwrite), None (Use Existing), Update (Use Existing, Get the Rest)
    # - pgn  - No (don't generate), Incremental (after getting a variation, do Pgn),
    #   After (after getting all vars, do Pgn)
    # - key (default) / noKey -  controls if the first "key" position
    #   in the variation is marked in the pgn
    # there are two arguments
    # - list of courses - get the course, get all chapters, then all
    #   variations for each course in course and course/variations
    # - list of variations - get the listed variations, and place in one-off/variations
    # there are a few environmental parameters
    # - set html root
    # - set pgn root
    # - set browser binary path
    # - set browser profile dir
    # - set browser profile name

    # set defaults
    WebFetch.doFetch = FetchMode.FETCH_NEW
    Pgn.doPgn = PgnMode.PGN_INCREMENTAL

    parser = _build_parser()
    try:
        args, unknown = parser.parse_known_args(sys.argv[1:])
    except argparse.ArgumentError as exc:
        print("- " + str(exc) + ".  Exiting.")
        return None, None, None

    processMode = args.processMode or "batch"

    courses, badCourses = _split_integer_tokens(args.courses)
    variations, badVariations = _split_integer_tokens(args.variations)

    if args.web is not None:
        webValue = args.web.lower()
        if webValue not in WebFetch.flagNames:
            print(
                "- Invalid argument <" + webValue + "> provided for web mode.  Exiting."
            )
            return None, None, None
        print("- Setting web mode to <" + webValue + ">")
        WebFetch.doFetch = FetchMode(WebFetch.flagNames.index(webValue))

    if args.key:
        Pgn.PGN_WRITE_KEY_MOVE = True

    if args.nokey:
        Pgn.PGN_WRITE_KEY_MOVE = False

    if args.pgn is not None:
        pgnValue = args.pgn.lower()
        if pgnValue not in Pgn.flagNames:
            print(
                "- Invalid argument <" + pgnValue + "> provided for pgn mode.  Exiting."
            )
            return None, None, None
        print("- Setting pgn mode to <" + pgnValue + ">")
        Pgn.doPgn = PgnMode(Pgn.flagNames.index(pgnValue))

    if args.pgnroot is not None:
        print("- Setting pgn root location to <" + args.pgnroot + ">")
        settings.chessable_pgn_cache = Path(args.pgnroot)

    if args.htmlroot is not None:
        print("- Setting html root location to <" + args.htmlroot + ">")
        settings.chessable_html_cache = Path(args.htmlroot)

    if args.browserbinary is not None:
        print("- Setting browser binary location to <" + args.browserbinary + ">")
        settings.firefox_binary_path = args.browserbinary

    if args.browserprofiledir is not None:
        print("- Setting browser profile directory to <" + args.browserprofiledir + ">")
        settings.firefox_automation_profile_dir = args.browserprofiledir

    # -browserprofile est ignoré (compatibilité) : consommé par argparse,
    # aucune action supplémentaire, comme dans l'ancien parsing.

    for token in badCourses + badVariations + unknown:
        print("- Don't know how to apply command line argument <" + token.lower() + ">")

    return processMode, courses, variations


@beartype
def getNextItemToProcess() -> tuple[bool, list[str] | None, list[str] | None]:
    """Boucle interactive : demande un cours ou une variation, puis les modes.

    Returns:
        Tuple ``(quitter, cours saisis, variations saisies)``. ``quitter`` est
        True si l'utilisateur a demandé à sortir ('q').
    """
    srcChoices = ["q", "c", "v"]
    cOut: list[str] = []
    vOut: list[str] = []

    s = ""
    while s not in srcChoices:
        s = input("- Enter 'c' for course, 'v' for variation, 'q' to quit: ")
        if s == "":
            s = "c"
        if s == "q":
            return True, None, None
        if s == "c":
            c = input("-- Enter the course ID: ")
            cOut.append(c)
        if s == "v":
            v = input("-- Enter the variation ID: ")
            vOut.append(v)

    s = "-1"
    while not utilities.is_integer(s) or int(s) not in range(len(WebFetch.flagNames)):
        s = input(
            "--- HTML - Fetch New HTML (1-default),"
            " refetch All HTML (2), use existing HTML (3), or quit (q)? "
        )
        if s == "q":
            return True, None, None
        # real range of values is 0-2, so have to use s-1
        WebFetch.doFetch = (
            FetchMode.FETCH_NEW
            if s == "-1" or not utilities.is_integer(s)
            else FetchMode(int(s) - 1)
        )
        s = str(WebFetch.doFetch.value)
    print("-- Web fetch mode set to " + WebFetch.flagNames[WebFetch.doFetch.value])

    s = "-1"
    while not utilities.is_integer(s) or int(s) not in range(len(Pgn.flagNames)):
        s = input(
            "--- Write PGN - Don't (1), During HTML Processing (2-default),"
            " After HTML Processing (3), or quit (q)? "
        )
        if s == "q":
            return True, None, None
        # real range of values is 0-2, so have to use s-1
        Pgn.doPgn = (
            PgnMode.PGN_INCREMENTAL
            if s == "-1" or not utilities.is_integer(s)
            else PgnMode(int(s) - 1)
        )
        s = str(Pgn.doPgn.value)
    print("-- PGN write mode set to " + Pgn.flagNames[Pgn.doPgn.value])

    return False, cOut, vOut
