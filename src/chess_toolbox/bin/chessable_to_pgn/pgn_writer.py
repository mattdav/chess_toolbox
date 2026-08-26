#!/usr/bin/env python3
"""Génération du contenu PGN à partir du HTML d'une variation Chessable.

Parcourt les éléments bs4 d'une variation pour en extraire l'en-tête, les
coups et les commentaires, et produit le texte PGN correspondant.

Portage du projet chessable-to-pgn de John DeMastri (MIT), v0.3,
chess@demastri.com.
"""

import enum
import re
from pathlib import Path
from typing import Any, ClassVar

from beartype import beartype
from bs4 import Tag

from chess_toolbox.config.settings import settings

from . import utilities
from .web_fetch import WebFetch

PGN_WRITE_KEY_MOVE = True

STARTING_POSITION = (
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"  # starting position
)

count: int = 0
firstMove: bool = True
firstMoveNbr: int = -1
lastSeenFenParts: list[str] = []
lastSeenSan: str = ""
keyWritten: bool = False


class PgnMode(enum.Enum):
    """Stratégie d'écriture des fichiers PGN."""

    #: N'écrit aucun PGN.
    PGN_NONE = 0
    #: Écrit le PGN au fur et à mesure, variation par variation.
    PGN_INCREMENTAL = 1
    #: Écrit le PGN une fois toutes les variations récupérées.
    PGN_AFTER = 2


class Pgn:
    """Génère le contenu PGN d'une variation Chessable à partir de son HTML."""

    PGN_NONE = PgnMode.PGN_NONE
    PGN_INCREMENTAL = PgnMode.PGN_INCREMENTAL
    PGN_AFTER = PgnMode.PGN_AFTER
    flagNames: ClassVar[list[str]] = ["none", "incremental", "after"]

    doPgn: ClassVar[PgnMode] = PgnMode.PGN_INCREMENTAL
    # Attribut dynamique positionné par command_line.py (-key / -nokey). Déclaré
    # ici uniquement pour le typage : la valeur par défaut suit le module.
    PGN_WRITE_KEY_MOVE: ClassVar[bool] = PGN_WRITE_KEY_MOVE

    def __init__(self) -> None:
        """Réinitialise le mode d'écriture PGN de la classe à ``PGN_INCREMENTAL``."""
        Pgn.doPgn = PgnMode.PGN_INCREMENTAL

    @classmethod
    @beartype
    def createPgnFromHtml(
        cls, courseId: str, variationId: str, variation: Tag | None, roundStr: str
    ) -> str | None:
        """Construit le PGN complet d'une variation à partir de sa page HTML.

        Args:
            courseId: Identifiant du cours Chessable.
            variationId: Identifiant de la variation.
            variation: Page HTML de la variation, ou None si non disponible.
            roundStr: Numéro de round PGN (ex: ``"2.4"``).

        Returns:
            Le PGN de la variation, ou None si le HTML n'a pas pu être exploité.
        """
        global count
        global firstMove
        global firstMoveNbr
        global keyWritten
        count = 0
        firstMove = True
        keyWritten = False
        firstMoveNbr = -1

        name, chapter, moves, term, inputFEN = WebFetch.getVariationParts(variation)

        if not chapter:
            print(" - HTML not found for variation")
            return None
        # getVariationParts() ne retourne jamais chapter non-vide sans aussi
        # renseigner moves/term/inputFEN : narrowing pour mypy uniquement.
        assert moves is not None and term is not None and inputFEN is not None
        if inputFEN != STARTING_POSITION:
            print("Variation does not begin at starting position")
        result = Pgn.getGameResult(term)
        moveBody = Pgn.buildMoveBody(moves, 0)
        inputFEN = Pgn.updateFEN(inputFEN)
        header = Pgn.buildHeader(
            courseId, variationId, name, chapter, result, roundStr, inputFEN
        )
        outPgn = header + moveBody
        # there's are two odd chessbase bugs in PGN Import -
        #   see included "ChessBase import issue.pgn":
        #  found In CB17, v37 - May '25
        # 1 - if there's are trailing comment(s) in a game
        #   (nothing after it but the game terminator)
        #  and just before the comment(s) is a variation, not a move,
        #  THEN these trailing comment(s) will render
        #  at the BEGINNING of the game, and depending on if the game
        #  started from a FEN provided position or not,
        #  any initial comments (before move 1) get mangled as well.
        #  (This one I actually saw in the original .Net version
        #  of the tool, and thought it was in my PGN generator, HA!)
        # 2 - if the last thing in a comment set (incl in variations)
        #   after a move is a number, CB consumes it and
        #   usually displays as move time - the only exception would be
        #   for %clk or %emt tags, which will never be in
        #   Chessable variations.
        # The workarounds, which are only slightly nasty are as follows:
        # 1 - look at the last things written as pgn if it's variation,
        #   comment ... n x comment ... comment terminator,
        #   then insert a null move prior to the last comment so it
        #   renders more correctly
        #   (CB ignores whitespace anyway, might make processing
        #   easier to concatenate comments (s/} {//)
        # 2 - look at the last item in any comment set.  If it's a
        #   number, tack on something ("_") so CB ignores it
        outPgn = outPgn.replace(
            "}  {", ""
        )  # clear sequential comments, CB ignores the whitespace...
        outPgn, allOpens, allCloses = insertNullMoveBeforeLastComment(outPgn)
        outPgn = escapeLastNumberInComments(outPgn, allOpens, allCloses)
        outPgn += Pgn.buildGameResult(result)
        return re.sub(r" +", " ", outPgn)

    @classmethod
    @beartype
    def updateFEN(cls, fen: str) -> str:
        """Remplace le compteur de coups d'un FEN par le premier numéro de coup joué.

        Args:
            fen: FEN de départ de la variation.

        Returns:
            FEN avec le compteur de demi-coups mis à jour.
        """
        global firstMoveNbr

        fenParts = fen.split()
        fenParts[5] = str(firstMoveNbr)
        return " ".join(fenParts)

    @classmethod
    @beartype
    def buildHeader(
        cls,
        courseId: str,
        variationId: str,
        name: str,
        chapter: list[Any],
        result: str,
        roundStr: str,
        FEN: str,
    ) -> str:
        """Construit les tags d'en-tête PGN (Event, Site, Round, White, Black...).

        Args:
            courseId: Identifiant du cours Chessable.
            variationId: Identifiant de la variation.
            name: Titre de la variation.
            chapter: Éléments de détail du chapitre (``<li>`` de la page variation).
            result: Résultat de la partie (ex: ``"1-0"``).
            roundStr: Numéro de round PGN.
            FEN: FEN de départ (avec compteur de coup mis à jour).

        Returns:
            Bloc d'en-tête PGN, terminé par une ligne vide.
        """

        # we have 6 pieces of info to be conveyed: course, chapter,
        #   variation title, variation url, location as round, and result
        # these can be mapped as:
        #  result => Result
        #  location => Round (4th var in 3rd chapter is 3.4)
        #  course title => Event
        #  variation URL => Site
        #  chapter name => White
        #  variation title => Black
        # Most viewers break the names into first and last based on the ',' character
        # We can prevent that by replacing any "," with '-'
        #   (can see if this looks ok...)
        courseTitle = re.sub(r"\s+", " ", chapter[0].text.replace("\n", "")).strip()
        chapterTitle = (
            re.sub(r"\s+", " ", chapter[2].text.replace("\n", ""))
            .strip()
            .replace(",", "-")
        )
        variationTitle = (
            re.sub(r"\s+", " ", name.replace("\n", "")).strip().replace(",", "-")
        )
        variationUrl = settings.base_chessable_url + "variation/" + str(variationId)

        header = (
            """[Event \""""
            + courseTitle
            + """\"]
[Site \""""
            + variationUrl
            + """/\"]
[Date \"????.??.??\"]
[Round \""""
            + roundStr
            + """\"]
[White \""""
            + chapterTitle
            + """\"]
[Black \""""
            + variationTitle
            + """\"]
[Result \""""
            + result
            + """\"]
"""
        )
        if FEN != STARTING_POSITION:
            header += '[FEN "' + FEN + '"]\n'
        header += "\n"

        return header

    @classmethod
    @beartype
    def buildMoveBody(cls, moves: list[Any], depth: int) -> str:
        """Construit récursivement le corps PGN (coups, commentaires, variations).

        Args:
            moves: Éléments HTML (spans/divs) de la séquence de coups à parcourir.
            depth: Profondeur courante dans l'arbre des variations imbriquées.

        Returns:
            Le texte PGN correspondant à ``moves`` et à ses enfants.
        """
        global count
        global firstMove
        global firstMoveNbr
        global lastSeenFenParts
        global lastSeenSan
        global keyWritten

        # Notes:
        #  c.text is actually recursive.  CommentInMove is not a PGN comment,
        #  contains both variations and comments!!
        #    when we know what we're working on, wrap variations in (), comments in {}
        #  ToDo: text has some formatting <h1>...that should be
        #  better represented in PGN comments (whether CB reads or not)
        outString = ""
        depth += 1
        count += 1
        # print(" " * depth + "x")
        outString = ""
        isWhite: bool = False

        for c in moves:
            if (
                c.name == "span"
                and c.get("class") is not None
                and "commentInVariation" in c["class"]
            ):
                outString += " { " + c.text + " } "
            if (
                c.name == "div"
                and c.get("class") is not None
                and ("openingNum" in c["class"] and Pgn.isTerminator(c.text))
            ):
                outString += "\n\n " + c.text + "\n\n"

            if (
                c.name == "div"
                and c.get("class") is not None
                and ("whiteMove" in c["class"] or "blackMove" in c["class"])
            ):
                keyStr = ""
                if PGN_WRITE_KEY_MOVE and "is_key" in c["class"]:
                    if not keyWritten:
                        keyWritten = True
                        keyStr = " { -KEY- } "

                if firstMove or "whiteMove" in c["class"]:
                    outString += c["data-move"] + " "
                    if firstMoveNbr < 0:
                        firstMoveNbr = int(c["data-move"][: c["data-move"].find(".")])
                    firstMove = False

                outString += keyStr + c["data-san"] + " "
                lastSeenSan = c["data-san"]
                lastSeenFenParts = c["data-fen"].split()
            if (
                c.name == "span"
                and c.get("class") is not None
                and "commentMoveSmall" in c["class"]
            ):
                if c.get("data-san") is not None:
                    fenParts = c["data-fen"].split()
                    if (
                        not firstMove and isWhite == fenParts[1]
                    ):  # two successive moves with the same color
                        print(" ### repeated move?? ### " + c["data-san"])
                    isWhite = fenParts[1] == "b"  # after this move...
                    moveNbr = c["data-mid"]
                    moveNbr = str(moveNbr)
                    if not moveNbr:
                        # data-mid absent for non-starting positions:
                        # derive from FEN fullmove
                        fullmove = int(fenParts[5])
                        moveNbr = str(fullmove if isWhite else fullmove - 1)
                    if firstMove and (
                        len(lastSeenFenParts) == 0 or fenParts[1] != lastSeenFenParts[1]
                    ):
                        # this is likely enough of a check...  repeat the last move seen
                        # this is a first move in a variation. it should be
                        # able to replace the last move seen
                        # if it's the next move. we need to repeat the prior move
                        # this can be seen at the end of a game, when the author
                        # provides a potential or actual continuation
                        # so it's a ply behind where this move thinks it is...
                        # print( "Mismatch onMove in variation ..." )
                        # print( lastSeenFenParts, fenParts )
                        moveNbr = moveNbr if not isWhite else str(int(moveNbr) - 1)
                        isWhite = not isWhite
                        outString += moveNbr
                        if isWhite:
                            outString += ". "
                        else:
                            outString += "... "
                        outString += lastSeenSan + " "
                        # ok, now set up to handle this actual move
                        firstMove = False
                        isWhite = not isWhite

                    if firstMove or isWhite:
                        outString += moveNbr
                        if isWhite:
                            outString += ". "
                        else:
                            outString += "... "
                        firstMove = False
                    outString += c["data-san"]
                    if Pgn.getNag(c.text) != "":
                        outString += Pgn.getNag(
                            c.text
                        )  # nag could be included in display text
                    outString += " "
            if (
                c.name == "span"
                and c.get("class") is not None
                and "annotation" in c["class"]
                and c.get("data-original-title") is not None
                and c["data-original-title"] != ""
                and Pgn.getNag(c.text) != ""
            ):
                outString = (
                    outString[:-1] + Pgn.getNag(c.text) + " "
                )  # or nag could be defined in a separate span

            # for embedded variations, write "(" then kids pgn, then ")"
            if (
                c.name == "span"
                and c.get("class") is not None
                and ("commentTopvar" in c["class"] or "commentSubvar" in c["class"])
            ):
                outString += " ( "
                firstMove = True

            # in any event, make sure we write any kid nodes' data
            kids = c.find_all(recursive=False)
            outString += Pgn.buildMoveBody(kids, depth)

            if (
                c.name == "span"
                and c.get("class") is not None
                and ("commentTopvar" in c["class"] or "commentSubvar" in c["class"])
            ):
                outString += " ) \n"

        # print(" " * depth + "/x")

        depth -= 1

        return outString

    @classmethod
    @beartype
    def getNag(cls, c: str) -> str:
        """Traduit un symbole d'annotation (``!``, ``?!``, ``±``...) en NAG PGN.

        Args:
            c: Texte contenant le symbole d'annotation en suffixe.

        Returns:
            Le NAG PGN correspondant (ex: ``" $1"``), ou chaîne vide si aucun
            symbole reconnu.
        """
        nagStrings = {
            "!": 1,
            "?": 2,
            "!!": 3,
            "??": 4,
            "!?": 5,
            "?!": 6,
            "=": 11,
            "∞": 13,
            "⩲": 14,
            "⩱": 15,
            "±": 16,
            "∓": 17,
            "+-": 18,
            "-+": 19,
            "⇆": 132,
        }

        if len(c) >= 2 and c[len(c) - 2 :] in nagStrings.keys():
            return " $" + str(nagStrings[c[len(c) - 2 :]])
        if len(c) >= 1 and c[len(c) - 1 :] in nagStrings.keys():
            return " $" + str(nagStrings[c[len(c) - 1 :]])
        # note, this can occur in the next child after the move text:
        #   <span class="annotation" data-original-title="Good move">!</span>
        return ""

    @classmethod
    @beartype
    def isTerminator(cls, s: str | None) -> bool:
        """Indique si un texte est un terminateur de partie PGN (``1-0``, ``*``...).

        Args:
            s: Texte à tester, ou None.

        Returns:
            True si ``s`` (une fois nettoyé) est un terminateur reconnu.
        """
        if s is None:
            return False
        termStrings = ["*", "1-0", "0-1", "1/2-1/2"]
        return s.strip() in termStrings

    @classmethod
    @beartype
    def writeCoursePgnFile(cls, courseId: str, pgnOut: str, incremental: bool) -> int:
        """Écrit (ou complète) le fichier PGN agrégé d'un cours.

        Args:
            courseId: Identifiant du cours Chessable.
            pgnOut: Contenu PGN à écrire.
            incremental: Si True, complète le fichier existant plutôt que de
                l'écraser.

        Returns:
            Nombre de caractères écrits.
        """
        course_path = settings.chessable_pgn_cache + "course/"
        mode = "a" if incremental else "w"
        path = Path(course_path)
        path.mkdir(parents=True, exist_ok=True)
        with open(course_path + courseId + ".pgn", mode, encoding="utf-8") as file:
            return file.write(pgnOut)

    @classmethod
    @beartype
    def writeVariationPgnFile(cls, variationId: str, pgnOut: str) -> int:
        """Écrit le fichier PGN d'une variation extraite isolément.

        Args:
            variationId: Identifiant de la variation.
            pgnOut: Contenu PGN à écrire.

        Returns:
            Nombre de caractères écrits.
        """
        variation_path = settings.chessable_pgn_cache + "variation/"
        path = Path(variation_path)
        path.mkdir(parents=True, exist_ok=True)
        with open(variation_path + variationId + ".pgn", "w", encoding="utf-8") as file:
            return file.write(pgnOut)

    @classmethod
    @beartype
    def buildGameResult(cls, result: str) -> str:
        """Formate le terminateur de partie PGN.

        Args:
            result: Résultat de la partie (ex: ``"1-0"``).

        Returns:
            Le résultat entouré de sauts de ligne, prêt à être concaténé au PGN.
        """
        return "\n " + result + " \n\n"

    @classmethod
    @beartype
    def getGameResult(cls, result: list[Any]) -> str:
        """Cherche le terminateur de partie parmi les éléments de fin de variation.

        Args:
            result: Éléments HTML susceptibles de contenir le terminateur.

        Returns:
            Le terminateur trouvé (ex: ``"1-0"``), ou ``"*"`` par défaut.
        """
        for x in result:
            if Pgn.isTerminator(x.text):
                return str(x.text)
        return "*"


@beartype
def insertNullMoveBeforeLastComment(pgn: str) -> tuple[str, list[int], list[int]]:
    """Insère un coup nul avant le dernier commentaire racine si nécessaire.

    Contourne un bug d'import ChessBase : quand une partie se termine par
    variation puis commentaire(s) au niveau racine, ces commentaires
    s'affichent au début de la partie. Insérer un coup nul (``Z0``) juste
    avant corrige le rendu.

    Args:
        pgn: Texte PGN généré pour une variation.

    Returns:
        Tuple ``(pgn corrigé, positions des accolades ouvrantes, positions
        des accolades fermantes)``.
    """
    # the specific case I'm looking for is if, at the root level,
    # the last things in the file are variation, then comment
    # if so, insert a null move just before the last comment
    iComment, allOpens, allCloses = findLastRootComment(pgn)
    lastMove, lastVariation, lastComment = findLastMove(pgn)
    if lastMove < lastVariation < lastComment:
        print(" - found a game with move - variation - comment ending")
        return pgn[:iComment] + " Z0 " + pgn[iComment:], allOpens, allCloses
    return pgn, allOpens, allCloses


@beartype
def escapeLastNumberInComments(pgn: str, opens: list[int], closes: list[int]) -> str:
    """Échappe les commentaires PGN se terminant par un nombre isolé.

    ChessBase interprète un nombre en fin de commentaire comme une durée de
    coup (``%clk``/``%emt``) : on ajoute un caractère neutre (``_``) pour
    l'empêcher de consommer ce nombre.

    Args:
        pgn: Texte PGN à corriger.
        opens: Positions des accolades ouvrantes de commentaire.
        closes: Positions des accolades fermantes de commentaire.

    Returns:
        Le PGN corrigé.
    """
    curStart = 0
    outPgn = ""
    curOpen: list[int] = []
    for thisClose in closes:
        while len(opens) > 0 and (len(curOpen) == 0 or opens[0] < thisClose):
            curOpen.append(opens[0])
            opens = opens[1:]
        thisOpen = curOpen.pop()
        # here thisopen, thisClose are the current nested comment we're dealing with.
        # if the next open is only 3 away "}  {", we don't have to worry about this pair
        if len(pgn) > thisClose + 3 and pgn[thisClose + 3] == "{":
            continue
        # ok - not followed by another comment, let's see if
        # the last elt in this set is a number
        parts = pgn[thisOpen:thisClose].split()
        if len(parts) > 0 and utilities.is_integer(parts[len(parts) - 1]):
            # we have to escape this.
            print(" Found a comment set ending in a number")
            outPgn = outPgn + pgn[curStart : thisClose + 1] + " { _ } "
            curStart = thisClose + 1
    outPgn = outPgn + pgn[curStart:]

    return outPgn


@beartype
def findLastRootComment(pgn: str) -> tuple[int, list[int], list[int]]:
    """Localise le dernier commentaire au niveau racine (hors variations).

    Args:
        pgn: Texte PGN à analyser.

    Returns:
        Tuple ``(position du dernier commentaire racine (-1 si aucun),
        positions des accolades ouvrantes, positions des accolades fermantes)``.
    """
    opens = []
    closes = []
    depth = 1
    curLast = -1
    for i in range(len(pgn)):
        ch = pgn[i]
        if ch == "(":
            depth += 1
        if ch == ")":
            depth -= 1
        if ch == "{":
            opens.append(i)
            if depth == 1:
                curLast = i
        if ch == "}":
            closes.append(i)
    return curLast, opens, closes


@beartype
def findLastRootVariation(pgn: str) -> int:
    """Localise la dernière variation ouverte au niveau racine.

    Args:
        pgn: Texte PGN à analyser.

    Returns:
        Position de la dernière parenthèse ouvrante racine (-1 si aucune).
    """
    depth = 1
    curLast = -1
    for i in range(len(pgn)):
        ch = pgn[i]
        if ch == "(":
            if depth == 1:
                curLast = i
            depth += 1
        if ch == ")":
            depth -= 1
    return curLast


@beartype
def findLastMove(pgn: str) -> tuple[int, int, int]:
    """Localise les indices (en tokens) du dernier coup, variation et commentaire.

    Args:
        pgn: Texte PGN à analyser.

    Returns:
        Tuple ``(index du dernier coup, index de la dernière variation, index
        du dernier commentaire)``, en index de token (-1 si absent).
    """
    lastMove = -1
    lastVariation = -1
    lastComment = -1

    inComment = False
    inVariation = False
    inTag = False

    depth = 1
    parts = pgn.split()
    for i in range(len(parts)):
        part = parts[i]

        if depth == 1 and part == "{":
            inComment = True
            lastComment = i
        elif depth == 1 and part == "}":
            inComment = False
        elif part == "(":
            if depth == 1:
                inVariation = True
                lastVariation = i
            depth += 1
        elif part == ")":
            depth -= 1
            if depth == 1:
                inVariation = False
        elif part.find("[") == 0 and not inTag:
            inTag = True
        elif part.find("]") == len(part) - 1 and inTag:
            inTag = False
        elif (
            depth == 1 and not inComment and not inVariation and not inTag
        ):  # possible move
            if part[len(part) - 1 :] == ".":  # move number
                continue
            if part.find("$") == 0:  # diacritic
                continue
            if part == "Z0":  # null move
                continue
            lastMove = i  # what else could it be...

    return lastMove, lastVariation, lastComment
