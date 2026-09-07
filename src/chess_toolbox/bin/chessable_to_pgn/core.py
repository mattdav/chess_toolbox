#!/usr/bin/env python3
"""
Filename: chessable-tp-pgn.py
Author: John DeMastri
Create Date: 2025-04-27
Version: 0.3
Description: Entry point and main workflow driver for the application

License: MIT License
Contact: chess@demastri.com
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from beartype import beartype
from bs4 import BeautifulSoup

from . import command_line
from .pgn_writer import Pgn, PgnMode
from .web_fetch import WebFetch

profileIds: list[str] = []


@dataclass
class ChapterResult:
    """Résultat du traitement d'un chapitre.

    Attributes:
        soup: Page HTML du chapitre, ou None si non disponible.
        variations: Tags des variations trouvées.
        expected: Nombre de variations attendu (oracle ``variationStats``),
            ou None si absent ou illisible.
        name: Titre du chapitre.
    """

    soup: BeautifulSoup | None
    variations: list[Any]
    expected: int | None
    name: str


@beartype
def main() -> None:
    """Point d'entrée principal : parse la ligne de commande et lance le traitement.

    Dispatch vers le mode ``interactive`` (boucle de saisie) ou ``batch``
    (traitement direct des cours/variations passés en argument).
    """
    print("Chessable-to-PGN tool (c) 2025 John DeMastri")

    print("--- starting ---")
    print(datetime.now())
    processMode, courses, variations = command_line.processCommandLineParams()
    if courses is None or variations is None or processMode is None:
        print("- Could not process command line parameters.  Exiting...")
        return

    if processMode == "interactive":
        quit = False
        while not quit:
            quit, courseId, variationId = command_line.getNextItemToProcess()
            # htmlOption: 1 = fetch new, 2 = fetch all, 3 = use existing (don't fetch)
            if not quit:
                processBatch(courseId or [], variationId or [])
                print(
                    "--- HTML: "
                    + WebFetch.flagNames[WebFetch.doFetch.value]
                    + " fetched\n--- PGN: "
                    + Pgn.flagNames[Pgn.doPgn.value]
                    + " written"
                )
    elif processMode == "batch":
        processBatch(courses, variations)
    else:
        print("unknown process mode <" + processMode + ">")

    print("--- complete ---")
    print(datetime.now())
    if processMode == "interactive":
        input("Exiting interactive mode!  Press ENTER to close this window.")


@beartype
def processBatch(courses: list[str], variations: list[str]) -> None:
    """Traite une liste de cours et de variations : fetch HTML + écriture PGN.

    Args:
        courses: Identifiants de cours Chessable à traiter.
        variations: Identifiants de variations isolées à traiter.
    """
    for courseId in courses:
        print(
            "--- Processing course "
            + courseId
            + " fetch: "
            + WebFetch.flagNames[WebFetch.doFetch.value]
            + " pgn: "
            + Pgn.flagNames[Pgn.doPgn.value]
        )
        # print("--- getting variation html ---")
        courseBS, chapters = loadCourseInfo(courseId)
        # this first pass loads/saves all of the chapter htmls
        # running single-threaded - an hour trying to get threading and
        # processing failed (selenium issues)
        print("----------")

        chapterResults = loadChapterInfo(courseId, chapters)
        # once we have the chapter details, we can load all of the variation htmls
        if Pgn.doPgn == PgnMode.PGN_INCREMENTAL:
            appendToFile = False
            for i in range(len(chapterResults)):
                vset = chapterResults[i].variations
                # get each variation individually
                for vi in range(len(vset)):
                    thisVarDet = WebFetch.getVariationDetailFromTag(
                        courseId, vset[vi], "Default"
                    )
                    thisVarDet.append(str(i + 1) + "." + str(vi + 1))
                    pgnOut = generateCoursePGNs(courseId, [thisVarDet])
                    Pgn.writeCoursePgnFile(courseId, pgnOut, appendToFile)
                    appendToFile = True
        elif Pgn.doPgn == PgnMode.PGN_AFTER:
            variationResults = loadVariationInfo(courseId, chapterResults)
            # now all of the variation htmls are available locally
            pgnOut = generateCoursePGNs(courseId, variationResults)
            Pgn.writeCoursePgnFile(courseId, pgnOut, False)
        else:
            # still get the html even if we're not doing pgn...
            loadVariationInfo(courseId, chapterResults)

        print("----------")

    for variationId in variations:
        courseId = "one-off"
        print(
            "--- Processing variation "
            + variationId
            + " fetch: "
            + WebFetch.flagNames[WebFetch.doFetch.value]
            + " pgn: "
            + Pgn.flagNames[Pgn.doPgn.value]
        )
        thisVarResult = WebFetch.getVariationDetailFromId(
            courseId, variationId, "Default"
        )
        if thisVarResult is None:
            continue
        thisVarResult.append("x.x")
        if Pgn.doPgn != PgnMode.PGN_NONE:
            # in this case there's no distinction between incremental / after
            pgnOut = generateCoursePGNs(courseId, [thisVarResult])
            Pgn.writeVariationPgnFile(variationId, pgnOut)


@beartype
def loadCourseInfo(courseId: str) -> tuple[BeautifulSoup | None, list[Any]]:
    """Récupère la page HTML d'un cours et affiche un résumé.

    Args:
        courseId: Identifiant du cours Chessable.

    Returns:
        Tuple ``(page cours, tags chapitre)``.
    """
    print("--- getting course html for course " + courseId + " ---")
    courseBS, chapters = WebFetch.getCourseDetail(courseId, "Default")
    print("----- found course '" + WebFetch.getCourseName(courseBS) + "'")
    print("----- read " + str(len(chapters)) + " chapters")
    return courseBS, chapters


@beartype
def loadChapterInfo(courseId: str, chapters: list[Any]) -> list[ChapterResult]:
    """Charge le détail HTML de chaque chapitre (jusqu'à 500).

    Args:
        courseId: Identifiant du cours Chessable.
        chapters: Tags chapitre résumés (page cours).

    Returns:
        Liste de ``ChapterResult`` par chapitre traité.
    """
    chapterResults: list[ChapterResult] = []

    chaptersRead = 0
    varsPreviewed = 0
    for c in chapters:
        thisResult = processChapter(courseId, str(c), "Default")
        varsPreviewed += len(thisResult.variations)
        chapterResults.append(thisResult)
        chaptersRead += 1
        if chaptersRead > 500:
            break
    print(" - total of " + str(varsPreviewed) + " - variations previewed - ")
    return chapterResults


@beartype
def loadVariationInfo(courseId: str, chapterResults: list[ChapterResult]) -> list[Any]:
    """Charge le détail HTML de chaque variation de chaque chapitre (jusqu'à 5000).

    Args:
        courseId: Identifiant du cours Chessable.
        chapterResults: Liste de ``ChapterResult`` par chapitre.

    Returns:
        Liste de ``[page variation, id variation, round]`` par variation lue.
    """
    variationResults = []

    variationsRead = 0
    chapterNbr = 0  # used to build round string
    variationNbr = 0  # used to build round string
    for chapterResult in chapterResults:
        chapterNbr += 1
        variationNbr = 0
        for variation in chapterResult.variations:
            variationNbr += 1
            thisVarDet = WebFetch.getVariationDetailFromTag(
                courseId, variation, "Default"
            )
            if thisVarDet[0] is None:
                print(" - no HTML found for variation " + thisVarDet[1])
                continue
            roundStr = str(chapterNbr) + "." + str(variationNbr)
            thisVarDet.append(roundStr)
            variationResults.append(thisVarDet)
            variationsRead += 1
            if variationsRead > 5000:
                break
        if variationsRead > 5000:
            break
    print(" - total of " + str(variationsRead) + " - variations read - ")
    return variationResults


@beartype
def generateCoursePGNs(courseId: str, variationResults: list[Any]) -> str:
    """Génère le PGN agrégé d'un ensemble de variations.

    Args:
        courseId: Identifiant du cours Chessable.
        variationResults: Liste de ``[page variation, id variation, round]``.

    Returns:
        Le PGN concaténé de toutes les variations valides.
    """
    print(" Writing Course PGN file for course " + courseId)
    aggregatePgn = ""
    for [variation, variationId, roundStr] in variationResults:
        pgnOut = Pgn.createPgnFromHtml(courseId, variationId, variation, roundStr)
        if pgnOut is not None:
            aggregatePgn += pgnOut
    return aggregatePgn


@beartype
def processChapter(courseId: str, tagStr: str, profileName: str) -> ChapterResult:
    """Reparse un tag chapitre et récupère ses variations.

    Args:
        courseId: Identifiant du cours Chessable.
        tagStr: HTML du tag ``div.chapter`` (sérialisé en chaîne).
        profileName: Profil navigateur à utiliser.

    Returns:
        Résultat du traitement du chapitre.
    """
    chapter = BeautifulSoup(tagStr, "html.parser")
    name = WebFetch.getChapterName(chapter)
    print("Parsing '" + name + "' (" + profileName + ") ")
    chapterBS, variations, expected = WebFetch.getChapterDetail(
        courseId, chapter, profileName
    )
    print(
        " returned  '"
        + name
        + "' had ("
        + profileName
        + ") "
        + str(len(variations))
        + " variations"
    )
    return ChapterResult(
        soup=chapterBS, variations=variations, expected=expected, name=name
    )


if __name__ == "__main__":
    main()
