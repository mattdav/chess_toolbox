"""Tests pour `chessable_to_pgn.core`."""

from collections.abc import Iterator
from typing import Any

import pytest
from bs4 import BeautifulSoup

from chess_toolbox.bin.chessable_to_pgn import command_line, core
from chess_toolbox.bin.chessable_to_pgn.core import (
    ChapterResult,
    generateCoursePGNs,
    loadChapterInfo,
    loadCourseInfo,
    loadVariationInfo,
    main,
    processBatch,
    processChapter,
)
from chess_toolbox.bin.chessable_to_pgn.pgn_writer import Pgn, PgnMode
from chess_toolbox.bin.chessable_to_pgn.web_fetch import FetchMode, WebFetch


@pytest.fixture(autouse=True)
def _reset_modes() -> Any:
    """Remet les modes globaux `WebFetch`/`Pgn` à leur état par défaut."""
    yield
    WebFetch.doFetch = FetchMode.FETCH_NEW
    Pgn.doPgn = PgnMode.PGN_INCREMENTAL


def _fail(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("cette fonction ne doit pas être appelée dans ce scénario")


class TestLoadCourseInfo:
    """Tests pour `loadCourseInfo`."""

    def test_returns_course_page_and_chapters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le tuple (page cours, chapitres) retourné par `WebFetch` est propagé."""
        courseBS = BeautifulSoup(
            "<title>Test Course - Chessable</title>", "html.parser"
        )
        monkeypatch.setattr(
            WebFetch,
            "getCourseDetail",
            lambda courseId, profileName: (courseBS, ["c1"]),
        )
        bs, chapters = loadCourseInfo("123")
        assert bs is courseBS
        assert chapters == ["c1"]


class TestLoadChapterInfo:
    """Tests pour `loadChapterInfo`."""

    def test_processes_each_chapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Chaque chapitre passé est traité via `processChapter`."""
        calls: list[str] = []

        def _fake_process_chapter(
            courseId: str, tagStr: str, profileName: str
        ) -> ChapterResult:
            calls.append(tagStr)
            return ChapterResult(
                soup=None, variations=["v1", "v2"], expected=None, name="chap"
            )

        monkeypatch.setattr(core, "processChapter", _fake_process_chapter)
        result = loadChapterInfo("123", ["chapA", "chapB"])
        assert calls == ["chapA", "chapB"]
        assert result == [
            ChapterResult(
                soup=None, variations=["v1", "v2"], expected=None, name="chap"
            ),
            ChapterResult(
                soup=None, variations=["v1", "v2"], expected=None, name="chap"
            ),
        ]


class TestGenerateCoursePGNs:
    """Tests pour `generateCoursePGNs`."""

    def test_aggregates_non_none_pgns_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Les variations sans PGN (`None`) sont ignorées dans l'agrégat."""
        monkeypatch.setattr(
            Pgn,
            "createPgnFromHtml",
            lambda courseId, variationId, variation, roundStr: (
                None if variationId == "skip" else f"[PGN {variationId}]"
            ),
        )
        result = generateCoursePGNs(
            "123",
            [[None, "keep", "1.1"], [None, "skip", "1.2"]],
        )
        assert result == "[PGN keep]"


class TestProcessChapter:
    """Tests pour `processChapter`."""

    def test_reparses_tag_and_returns_page_and_variations(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le tag est reparsé et le détail du chapitre est retourné."""
        tag_str = (
            '<div class="chapter"><a href="/course/123/45">x</a>'
            '<div class="toBeClamped title">Test Chapter</div></div>'
        )
        chapterBS = BeautifulSoup("<title>chapter page</title>", "html.parser")
        monkeypatch.setattr(
            WebFetch,
            "getChapterDetail",
            lambda courseId, chapter, profileName: (chapterBS, ["var1"], None),
        )
        result = processChapter("123", tag_str, "Default")
        assert result.soup is chapterBS
        assert result.variations == ["var1"]
        assert result.name == "Test Chapter"
        assert result.expected is None


class TestLoadVariationInfo:
    """Tests pour `loadVariationInfo`."""

    def test_builds_round_string_and_skips_missing_html(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le round (chapitre.variation) est calculé, les HTML absents ignorés."""
        variation_ok = BeautifulSoup(
            '<div><a href="/variation/38877075/some-name">Some Name</a></div>',
            "html.parser",
        ).find("div")
        variation_missing = BeautifulSoup(
            '<div><a href="/variation/11111111/other-name">Other Name</a></div>',
            "html.parser",
        ).find("div")
        variationBS = BeautifulSoup("<title>variation page</title>", "html.parser")

        def _fake_get_variation_html(
            variationId: str, courseId: str, profileName: str
        ) -> BeautifulSoup | None:
            return variationBS if variationId == "38877075" else None

        monkeypatch.setattr(WebFetch, "getVariationHtml", _fake_get_variation_html)

        chapterResults = [
            ChapterResult(
                soup=None,
                variations=[variation_ok, variation_missing],
                expected=None,
                name="chap1",
            ),
            ChapterResult(
                soup=None, variations=[variation_ok], expected=None, name="chap2"
            ),
        ]
        result = loadVariationInfo("123", chapterResults)

        assert result == [
            [variationBS, "38877075", "1.1"],
            [variationBS, "38877075", "2.1"],
        ]


class TestProcessBatch:
    """Tests pour `processBatch`, orchestrateur principal du traitement par lot."""

    def _patch_course_and_chapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(core, "loadCourseInfo", lambda courseId: (None, ["chap1"]))
        monkeypatch.setattr(
            core,
            "loadChapterInfo",
            lambda courseId, chapters: [
                ChapterResult(
                    soup=None, variations=["var1", "var2"], expected=None, name="chap1"
                )
            ],
        )

    def test_incremental_mode_writes_one_pgn_per_variation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode incrémental, chaque variation déclenche une écriture PGN."""
        self._patch_course_and_chapter(monkeypatch)
        Pgn.doPgn = PgnMode.PGN_INCREMENTAL
        monkeypatch.setattr(
            WebFetch,
            "getVariationDetailFromTag",
            lambda courseId, variationBs, profileName: [None, variationBs],
        )
        monkeypatch.setattr(core, "generateCoursePGNs", lambda courseId, results: "PGN")
        writes: list[bool] = []

        def _write_course(courseId: str, pgnOut: str, incremental: bool) -> int:
            writes.append(incremental)
            return 3

        monkeypatch.setattr(Pgn, "writeCoursePgnFile", _write_course)

        processBatch(["123"], [])

        assert writes == [False, True]

    def test_after_mode_writes_a_single_aggregated_pgn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode after, un seul PGN agrégé est écrit après toutes les variations."""
        self._patch_course_and_chapter(monkeypatch)
        Pgn.doPgn = PgnMode.PGN_AFTER
        monkeypatch.setattr(
            core, "loadVariationInfo", lambda courseId, chapterResults: ["fake result"]
        )
        generate_calls: list[list[Any]] = []

        def _generate(courseId: str, results: list[Any]) -> str:
            generate_calls.append(results)
            return "PGN"

        monkeypatch.setattr(core, "generateCoursePGNs", _generate)
        writes: list[bool] = []

        def _write_course(courseId: str, pgnOut: str, incremental: bool) -> int:
            writes.append(incremental)
            return 3

        monkeypatch.setattr(Pgn, "writeCoursePgnFile", _write_course)

        processBatch(["123"], [])

        assert generate_calls == [["fake result"]]
        assert writes == [False]

    def test_none_mode_only_fetches_html_without_writing_pgn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode none, le HTML est chargé mais aucun PGN n'est généré ou écrit."""
        self._patch_course_and_chapter(monkeypatch)
        Pgn.doPgn = PgnMode.PGN_NONE
        fetch_calls: list[Any] = []

        def _load_variation_info(courseId: str, chapterResults: list[Any]) -> list[Any]:
            fetch_calls.append(chapterResults)
            return []

        monkeypatch.setattr(core, "loadVariationInfo", _load_variation_info)
        monkeypatch.setattr(core, "generateCoursePGNs", _fail)
        monkeypatch.setattr(Pgn, "writeCoursePgnFile", _fail)

        processBatch(["123"], [])

        assert fetch_calls == [
            [
                ChapterResult(
                    soup=None, variations=["var1", "var2"], expected=None, name="chap1"
                )
            ]
        ]

    def test_one_off_variation_writes_pgn_when_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Une variation isolée trouvée écrit un fichier PGN dédié."""
        Pgn.doPgn = PgnMode.PGN_INCREMENTAL
        monkeypatch.setattr(
            WebFetch,
            "getVariationDetailFromId",
            lambda courseId, variationID, profileName: [None, variationID],
        )
        monkeypatch.setattr(core, "generateCoursePGNs", lambda courseId, results: "PGN")
        writes: list[str] = []

        def _write_variation(variationId: str, pgnOut: str) -> int:
            writes.append(variationId)
            return 3

        monkeypatch.setattr(Pgn, "writeVariationPgnFile", _write_variation)

        processBatch([], ["v1"])

        assert writes == ["v1"]

    def test_one_off_variation_skipped_when_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Une variation isolée introuvable (`None`) est ignorée sans erreur."""
        monkeypatch.setattr(
            WebFetch,
            "getVariationDetailFromId",
            lambda courseId, variationID, profileName: None,
        )
        monkeypatch.setattr(core, "generateCoursePGNs", _fail)
        monkeypatch.setattr(Pgn, "writeVariationPgnFile", _fail)

        processBatch([], ["v1"])


class TestMain:
    """Tests pour `main`, point d'entrée dispatchant batch/interactive."""

    def test_aborts_when_command_line_params_invalid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Des paramètres invalides arrêtent `main` sans rien traiter."""
        monkeypatch.setattr(
            command_line, "processCommandLineParams", lambda: (None, None, None)
        )
        monkeypatch.setattr(core, "processBatch", _fail)
        main()

    def test_batch_mode_delegates_to_process_batch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le mode batch délègue directement à `processBatch`."""
        monkeypatch.setattr(
            command_line, "processCommandLineParams", lambda: ("batch", ["1"], ["2"])
        )
        calls: list[tuple[list[str], list[str]]] = []
        monkeypatch.setattr(
            core,
            "processBatch",
            lambda courses, variations: calls.append((courses, variations)),
        )
        main()
        assert calls == [(["1"], ["2"])]

    def test_interactive_mode_loops_until_quit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le mode interactif traite chaque item saisi jusqu'au 'quitter'."""
        monkeypatch.setattr(
            command_line,
            "processCommandLineParams",
            lambda: ("interactive", [], []),
        )
        responses: Iterator[tuple[bool, list[str] | None, list[str] | None]] = iter(
            [(False, ["1"], []), (True, None, None)]
        )
        monkeypatch.setattr(
            command_line, "getNextItemToProcess", lambda: next(responses)
        )
        calls: list[tuple[list[str], list[str]]] = []
        monkeypatch.setattr(
            core,
            "processBatch",
            lambda courses, variations: calls.append((courses, variations)),
        )
        monkeypatch.setattr("builtins.input", lambda _prompt="": "")
        main()
        assert calls == [(["1"], [])]

    def test_unknown_process_mode_does_not_process_batch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un mode de traitement inconnu n'appelle pas `processBatch`."""
        monkeypatch.setattr(
            command_line, "processCommandLineParams", lambda: ("bogus", [], [])
        )
        monkeypatch.setattr(core, "processBatch", _fail)
        main()
