"""Tests pour `chessable_to_pgn.web_fetch`.

Les fonctions dépendant réellement de Selenium (`_build_browser`,
`loadHtmlFromWeb`, `start_automation_browser`, `login_and_save_cookies`) sont
volontairement laissées hors périmètre : les tester nécessiterait soit un
vrai navigateur, soit un mock si profond qu'il ne testerait plus rien de
significatif.
"""

import time
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup, Tag

from chess_toolbox.bin.chessable_to_pgn import web_fetch
from chess_toolbox.bin.chessable_to_pgn.web_fetch import (
    ChessableAuthError,
    ChessableFetcher,
    FetchMode,
    WebFetch,
    _as_tag,
    _assert_not_redirected,
    _attr_str,
    _clear_lock_files,
    _find_geckodriver,
    _is_public_page,
    _persistent_profile_dir,
    ensure_session,
)
from chess_toolbox.config.settings import settings

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(autouse=True)
def _reset_webfetch_state() -> Any:
    """Remet `WebFetch.doFetch`/`WebFetch.browser` à leur état par défaut."""
    yield
    WebFetch.doFetch = FetchMode.FETCH_NEW
    WebFetch.browser = None


def test_is_public_page_detects_public_html() -> None:
    """Le HTML de la page d'accueil publique est reconnu comme tel."""
    html = (FIXTURES_DIR / "chessable_public_page.html").read_text(encoding="utf-8")
    assert _is_public_page(html) is True


def test_is_public_page_rejects_authenticated_html() -> None:
    """Un HTML de contenu authentifié n'est pas confondu avec la page publique."""
    html = "<html><head><title>Course Dashboard</title></head><body></body></html>"
    assert _is_public_page(html) is False


def test_is_public_page_rejects_none() -> None:
    """Un HTML absent (None) n'est pas une page publique."""
    assert _is_public_page(None) is False


class _FakeBrowser:
    """Double minimal exposant seulement `current_url`."""

    def __init__(self, current_url: str) -> None:
        self.current_url = current_url
        self.quit_called = False

    def get(self, _url: str) -> None:
        pass

    def quit(self) -> None:
        self.quit_called = True


class TestAssertNotRedirected:
    """Tests pour `_assert_not_redirected`."""

    def test_accepts_matching_url(self) -> None:
        """Aucune exception si l'URL courante correspond à l'URL attendue."""
        browser = _FakeBrowser("https://www.chessable.com/profile/")
        _assert_not_redirected(browser, "https://www.chessable.com/profile/")  # type: ignore[arg-type]

    def test_ignores_trailing_slash_difference(self) -> None:
        """Une différence de slash final seul n'est pas une redirection."""
        browser = _FakeBrowser("https://www.chessable.com/profile")
        _assert_not_redirected(browser, "https://www.chessable.com/profile/")  # type: ignore[arg-type]

    def test_raises_on_redirect(self) -> None:
        """Une URL différente lève `ChessableAuthError`."""
        browser = _FakeBrowser("https://www.chessable.com/")
        with pytest.raises(ChessableAuthError):
            _assert_not_redirected(browser, "https://www.chessable.com/profile/")  # type: ignore[arg-type]


class TestAsTag:
    """Tests pour `_as_tag`."""

    def test_returns_tag_unchanged(self) -> None:
        """Un `Tag` est retourné tel quel."""
        soup = BeautifulSoup("<div>x</div>", "html.parser")
        tag = soup.find("div")
        assert _as_tag(tag, "contexte") is tag

    def test_raises_on_none(self) -> None:
        """`None` lève `ValueError`."""
        with pytest.raises(ValueError, match="contexte"):
            _as_tag(None, "contexte")

    def test_raises_on_navigable_string(self) -> None:
        """Un `NavigableString` (texte brut) lève `ValueError`."""
        soup = BeautifulSoup("<div>x</div>", "html.parser")
        div = soup.find("div")
        assert isinstance(div, Tag)
        text_node = div.contents[0]
        with pytest.raises(ValueError, match="contexte"):
            _as_tag(text_node, "contexte")  # type: ignore[arg-type]


class TestAttrStr:
    """Tests pour `_attr_str`."""

    def test_returns_string_attribute(self) -> None:
        """Un attribut simple chaîne est retourné tel quel."""
        soup = BeautifulSoup('<a href="/x">t</a>', "html.parser")
        tag = soup.find("a")
        assert isinstance(tag, Tag)
        assert _attr_str(tag, "href") == "/x"

    def test_raises_on_missing_attribute(self) -> None:
        """Un attribut absent lève `ValueError`."""
        soup = BeautifulSoup("<a>t</a>", "html.parser")
        tag = soup.find("a")
        assert isinstance(tag, Tag)
        with pytest.raises(ValueError, match="href"):
            _attr_str(tag, "href")

    def test_raises_on_multivalued_attribute(self) -> None:
        """Un attribut multi-valué (ex: `class`) lève `ValueError`."""
        soup = BeautifulSoup('<a class="a b">t</a>', "html.parser")
        tag = soup.find("a")
        assert isinstance(tag, Tag)
        with pytest.raises(ValueError, match="class"):
            _attr_str(tag, "class")


class TestPersistentProfileDir:
    """Tests pour `_persistent_profile_dir`."""

    def test_creates_and_returns_configured_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le dossier configuré est créé s'il n'existe pas, puis retourné."""
        target = tmp_path / "does" / "not" / "exist"
        monkeypatch.setattr(settings, "firefox_automation_profile_dir", str(target))
        result = _persistent_profile_dir()
        assert result == target
        assert target.is_dir()


class TestClearLockFiles:
    """Tests pour `_clear_lock_files`."""

    def test_removes_existing_lock_files(self, tmp_path: Path) -> None:
        """Les fichiers `lock` et `.parentlock` présents sont supprimés."""
        (tmp_path / "lock").write_text("x", encoding="utf-8")
        (tmp_path / ".parentlock").write_text("x", encoding="utf-8")
        _clear_lock_files(str(tmp_path))
        assert not (tmp_path / "lock").exists()
        assert not (tmp_path / ".parentlock").exists()

    def test_no_error_when_no_lock_files(self, tmp_path: Path) -> None:
        """Un dossier sans fichiers de verrou ne lève aucune erreur."""
        _clear_lock_files(str(tmp_path))


class TestFindGeckodriver:
    """Tests pour `_find_geckodriver`."""

    def test_returns_configured_path_when_it_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le chemin configuré est retourné s'il existe sur disque."""
        driver = tmp_path / "geckodriver.exe"
        driver.write_text("x", encoding="utf-8")
        monkeypatch.setattr(settings, "geckodriver_path", str(driver))
        assert _find_geckodriver() == str(driver)

    def test_returns_none_when_configured_path_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un chemin configuré mais absent du disque retourne None."""
        monkeypatch.setattr(settings, "geckodriver_path", str(tmp_path / "nope.exe"))
        assert _find_geckodriver() is None

    def test_returns_none_when_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Aucune configuration retourne None."""
        monkeypatch.setattr(settings, "geckodriver_path", "")
        assert _find_geckodriver() is None


class TestLoadWriteHtmlFile:
    """Tests pour `loadHtmlFromFile`/`writeHtmlToFile`."""

    def test_load_returns_empty_string_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un chemin absent du cache retourne une chaîne vide."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        assert WebFetch.loadHtmlFromFile("course/123") == ""

    def test_write_then_load_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le contenu écrit est relu identique."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        WebFetch.writeHtmlToFile("course/123", "<html>hi</html>")
        assert WebFetch.loadHtmlFromFile("course/123") == "<html>hi</html>"

    def test_write_with_none_content_writes_empty_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un contenu `None` produit un fichier vide (pas d'exception)."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        WebFetch.writeHtmlToFile("course/123", None)
        assert WebFetch.loadHtmlFromFile("course/123") == ""

    def test_write_creates_nested_parent_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un emplacement à plusieurs niveaux crée tous les parents manquants."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        WebFetch.writeHtmlToFile("course/123/variation/456", "<html>v</html>")
        assert WebFetch.loadHtmlFromFile("course/123/variation/456") == "<html>v</html>"
        assert (tmp_path / "course" / "123" / "variation" / "456.html").is_file()


class TestGetChapterExpectedCount:
    """Tests pour `WebFetch.getChapterExpectedCount` (oracle variationStats)."""

    def test_nominal_count(self) -> None:
        """Le format standard `"trouvées/attendues variations"` est lu correctement."""
        html = (
            '<div class="chapter"><div class="variationStats">'
            "0/14 variations</div></div>"
        )
        tag = BeautifulSoup(html, "html.parser").find("div", class_="chapter")
        assert isinstance(tag, Tag)
        assert WebFetch.getChapterExpectedCount(tag) == 14

    def test_singular_count(self) -> None:
        """Le format singulier `"1/1 variation"` est lu correctement."""
        html = (
            '<div class="chapter"><div class="variationStats">1/1 variation</div></div>'
        )
        tag = BeautifulSoup(html, "html.parser").find("div", class_="chapter")
        assert isinstance(tag, Tag)
        assert WebFetch.getChapterExpectedCount(tag) == 1

    def test_missing_stats_returns_none(self) -> None:
        """L'absence de `div.variationStats` retourne None sans lever d'exception."""
        html = '<div class="chapter"></div>'
        tag = BeautifulSoup(html, "html.parser").find("div", class_="chapter")
        assert isinstance(tag, Tag)
        assert WebFetch.getChapterExpectedCount(tag) is None

    def test_unparsable_text_returns_none(self) -> None:
        """Un texte sans motif `chiffres/chiffres` retourne None."""
        html = (
            '<div class="chapter"><div class="variationStats">'
            "plusieurs variations</div></div>"
        )
        tag = BeautifulSoup(html, "html.parser").find("div", class_="chapter")
        assert isinstance(tag, Tag)
        assert WebFetch.getChapterExpectedCount(tag) is None


class TestGetChapterDetailRetry:
    """Tests pour la boucle de nouvelle tentative de `getChapterDetail`."""

    def _chapter_tag(self, stats_text: str) -> Tag:
        html = (
            '<div class="chapter">'
            '<a href="https://www.chessable.com/course/123/chapter/456">chap</a>'
            f'<div class="variationStats">{stats_text}</div>'
            "</div>"
        )
        tag = BeautifulSoup(html, "html.parser").find("div", class_="chapter")
        assert isinstance(tag, Tag)
        return tag

    def _page_with_variations(self, count: int) -> BeautifulSoup:
        cards = "".join(
            f'<div class="variation-card__row--main">v{i}</div>' for i in range(count)
        )
        return BeautifulSoup(f"<html><body>{cards}</body></html>", "html.parser")

    def test_retries_until_expected_count_reached(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un chapitre incomplet est retenté jusqu'à atteindre le compte attendu."""
        pages = [self._page_with_variations(1), self._page_with_variations(2)]
        calls: list[bool] = []

        def _fake_get_chapter_html(
            courseId: str, chapterId: str, profileName: str, forceFetch: bool = False
        ) -> BeautifulSoup:
            calls.append(forceFetch)
            return pages[len(calls) - 1]

        monkeypatch.setattr(WebFetch, "getChapterHtml", _fake_get_chapter_html)
        WebFetch.doFetch = FetchMode.FETCH_NEW

        bs, variations, expected = WebFetch.getChapterDetail(
            "123", self._chapter_tag("0/2 variations"), "Default"
        )

        assert expected == 2
        assert len(variations) == 2
        assert calls == [False, True]

    def test_stops_after_three_attempts_when_still_incomplete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un chapitre qui reste incomplet s'arrête après 3 tentatives au total."""
        calls: list[bool] = []

        def _fake_get_chapter_html(
            courseId: str, chapterId: str, profileName: str, forceFetch: bool = False
        ) -> BeautifulSoup:
            calls.append(forceFetch)
            return self._page_with_variations(1)

        monkeypatch.setattr(WebFetch, "getChapterHtml", _fake_get_chapter_html)
        WebFetch.doFetch = FetchMode.FETCH_NEW

        bs, variations, expected = WebFetch.getChapterDetail(
            "123", self._chapter_tag("0/5 variations"), "Default"
        )

        assert expected == 5
        assert len(variations) == 1
        assert calls == [False, True, True]

    def test_no_retry_when_expected_count_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sans oracle lisible, aucune nouvelle tentative n'est déclenchée."""
        calls: list[bool] = []

        def _fake_get_chapter_html(
            courseId: str, chapterId: str, profileName: str, forceFetch: bool = False
        ) -> BeautifulSoup:
            calls.append(forceFetch)
            return self._page_with_variations(1)

        monkeypatch.setattr(WebFetch, "getChapterHtml", _fake_get_chapter_html)
        WebFetch.doFetch = FetchMode.FETCH_NEW

        bs, variations, expected = WebFetch.getChapterDetail(
            "123", self._chapter_tag("texte illisible"), "Default"
        )

        assert expected is None
        assert calls == [False]

    def test_no_retry_in_fetch_none_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """En mode FETCH_NONE, un chapitre incomplet n'est jamais retenté."""
        calls: list[bool] = []

        def _fake_get_chapter_html(
            courseId: str, chapterId: str, profileName: str, forceFetch: bool = False
        ) -> BeautifulSoup:
            calls.append(forceFetch)
            return self._page_with_variations(1)

        monkeypatch.setattr(WebFetch, "getChapterHtml", _fake_get_chapter_html)
        WebFetch.doFetch = FetchMode.FETCH_NONE

        bs, variations, expected = WebFetch.getChapterDetail(
            "123", self._chapter_tag("0/5 variations"), "Default"
        )

        assert expected == 5
        assert len(variations) == 1
        assert calls == [False]


class TestGetHtml:
    """Tests pour `getHtml`, avec `_fetchHtml` remplacé par un double."""

    def test_fetch_all_always_calls_fetch_and_writes_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode `FETCH_ALL`, le réseau est interrogé même si un cache existe."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        WebFetch.writeHtmlToFile("course/123", "<html>stale cache</html>")
        monkeypatch.setattr(
            WebFetch,
            "_fetchHtml",
            lambda url, profile, isVar, pageKind: "<html>fresh</html>",
        )
        WebFetch.doFetch = FetchMode.FETCH_ALL

        result = WebFetch.getHtml("course", "123", "profile")

        assert result is not None
        assert "fresh" in str(result)
        assert WebFetch.loadHtmlFromFile("course/123") == "<html>fresh</html>"

    def test_fetch_new_reuses_existing_cache_without_network(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode `FETCH_NEW`, un cache déjà présent est utilisé sans appel réseau."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        WebFetch.writeHtmlToFile("course/123", "<html>cached</html>")

        def _fail(*_args: Any, **_kwargs: Any) -> str:
            raise AssertionError(
                "_fetchHtml ne doit pas être appelé quand le cache existe"
            )

        monkeypatch.setattr(WebFetch, "_fetchHtml", _fail)
        WebFetch.doFetch = FetchMode.FETCH_NEW

        result = WebFetch.getHtml("course", "123", "profile")

        assert result is not None
        assert "cached" in str(result)

    def test_fetch_new_fetches_when_cache_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode `FETCH_NEW`, l'absence de cache déclenche un fetch réseau."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        monkeypatch.setattr(
            WebFetch,
            "_fetchHtml",
            lambda url, profile, isVar, pageKind: "<html>from web</html>",
        )
        WebFetch.doFetch = FetchMode.FETCH_NEW

        result = WebFetch.getHtml("course", "123", "profile")

        assert result is not None
        assert "from web" in str(result)
        assert WebFetch.loadHtmlFromFile("course/123") == "<html>from web</html>"

    def test_fetch_none_returns_none_when_cache_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En mode `FETCH_NONE`, l'absence de cache retourne None sans appel réseau."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)

        def _fail(*_args: Any, **_kwargs: Any) -> str:
            raise AssertionError(
                "_fetchHtml ne doit pas être appelé en mode FETCH_NONE"
            )

        monkeypatch.setattr(WebFetch, "_fetchHtml", _fail)
        WebFetch.doFetch = FetchMode.FETCH_NONE

        assert WebFetch.getHtml("course", "123", "profile") is None

    def test_poisoned_public_page_cache_is_refetched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un cache contenant la page publique (session expirée) est refetché."""
        monkeypatch.setattr(settings, "chessable_html_cache", tmp_path)
        public_html = (FIXTURES_DIR / "chessable_public_page.html").read_text(
            encoding="utf-8"
        )
        WebFetch.writeHtmlToFile("course/123", public_html)
        monkeypatch.setattr(
            WebFetch,
            "_fetchHtml",
            lambda url, profile, isVar, pageKind: "<html>real content</html>",
        )
        WebFetch.doFetch = FetchMode.FETCH_NEW

        result = WebFetch.getHtml("course", "123", "profile")

        assert result is not None
        assert "real content" in str(result)


class TestGetCourseChapters:
    """Tests pour `getCourseChapters`, sur le fixture réel de page cours."""

    def test_finds_all_chapter_tags(self) -> None:
        """Les trois chapitres du fixture sont retournés."""
        html = (FIXTURES_DIR / "course_page.html").read_text(encoding="utf-8")
        bs = BeautifulSoup(html, "html.parser")
        chapters = WebFetch.getCourseChapters(bs)
        assert len(chapters) == 3


class TestGetCourseName:
    """Tests pour `getCourseName`."""

    def test_extracts_name_from_title(self) -> None:
        """Le nom du cours est extrait du `<title>`, sans le suffixe ` - Chessable`."""
        html = (FIXTURES_DIR / "course_page.html").read_text(encoding="utf-8")
        bs = BeautifulSoup(html, "html.parser")
        assert WebFetch.getCourseName(bs) == "Alex Banzea's London System"

    def test_returns_placeholder_when_bs_is_none(self) -> None:
        """L'absence de page retourne un texte de repli plutôt qu'une exception."""
        assert WebFetch.getCourseName(None) == "<No Course HTML Available>"


class TestGetChapterName:
    """Tests pour `getChapterName`, sur un chapitre extrait du fixture réel."""

    def test_extracts_title(self) -> None:
        """Le titre du premier chapitre du fixture est extrait correctement."""
        html = (FIXTURES_DIR / "course_page.html").read_text(encoding="utf-8")
        bs = BeautifulSoup(html, "html.parser")
        chapters = WebFetch.getCourseChapters(bs)
        assert WebFetch.getChapterName(chapters[0]) == "Introduction"


class TestGetChapterVariations:
    """Tests pour `getChapterVariations`, sur un extrait synthétique de page."""

    def test_finds_variation_rows(self) -> None:
        """Les lignes de variation sont retrouvées via leur classe CSS."""
        html = """
        <div id="root">
          <div class="variation-card__row--main"><a href="/variation/1/">A</a></div>
          <div class="variation-card__row--main"><a href="/variation/2/">B</a></div>
          <div class="not-a-variation">C</div>
        </div>
        """
        bs = BeautifulSoup(html, "html.parser")
        variations = WebFetch.getChapterVariations(bs)
        assert len(variations) == 2

    def test_returns_empty_list_when_bs_is_none(self) -> None:
        """L'absence de page retourne une liste vide plutôt qu'une exception."""
        assert WebFetch.getChapterVariations(None) == []


class TestEnsureSession:
    """Tests pour `ensure_session`, avec attente et `time.sleep` mockés."""

    class _InstantTimeoutWait:
        """Double de `WebDriverWait` qui échoue immédiatement (pas d'attente réelle)."""

        def __init__(self, driver: Any, timeout: float) -> None:
            pass

        def until(self, condition: Any) -> None:
            raise TimeoutError("no real polling in tests")

    def test_raises_runtime_error_when_browser_not_initialized(self) -> None:
        """Un appel hors bloc `ChessableFetcher` (browser=None) lève `RuntimeError`."""
        WebFetch.browser = None
        with pytest.raises(RuntimeError):
            ensure_session()

    def test_passes_when_url_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Une session valide (pas de redirection) ne lève aucune exception."""
        monkeypatch.setattr(web_fetch, "WebDriverWait", self._InstantTimeoutWait)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        profile_url = settings.base_chessable_url + "profile/"
        WebFetch.browser = _FakeBrowser(profile_url)  # type: ignore[assignment]

        ensure_session()

    def test_raises_auth_error_when_redirected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Une redirection hors de la page profil lève `ChessableAuthError`."""
        monkeypatch.setattr(web_fetch, "WebDriverWait", self._InstantTimeoutWait)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        WebFetch.browser = _FakeBrowser(settings.base_chessable_url)  # type: ignore[assignment]

        with pytest.raises(ChessableAuthError):
            ensure_session()


class TestChessableFetcher:
    """Tests pour `ChessableFetcher.__enter__`/`__exit__`, `_build_browser` remplacé."""

    def test_enter_assigns_browser_and_verifies_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Une session valide assigne `WebFetch.browser` et retourne le gestionnaire."""
        monkeypatch.setattr(settings, "firefox_automation_profile_dir", str(tmp_path))
        profile_url = settings.base_chessable_url + "profile/"
        fake_browser: Any = _FakeBrowser(profile_url)
        monkeypatch.setattr(
            WebFetch,
            "_build_browser",
            lambda profile_dir, profile_name="": fake_browser,
        )
        monkeypatch.setattr(
            web_fetch, "WebDriverWait", TestEnsureSession._InstantTimeoutWait
        )
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        with ChessableFetcher() as fetcher:
            assert isinstance(fetcher, ChessableFetcher)
            assert id(WebFetch.browser) == id(fake_browser)

        assert fake_browser.quit_called is True
        assert WebFetch.browser is None

    def test_enter_closes_browser_and_reraises_on_auth_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Une session invalide ferme le navigateur puis propage l'exception."""
        monkeypatch.setattr(settings, "firefox_automation_profile_dir", str(tmp_path))
        fake_browser: Any = _FakeBrowser(settings.base_chessable_url)
        monkeypatch.setattr(
            WebFetch,
            "_build_browser",
            lambda profile_dir, profile_name="": fake_browser,
        )
        monkeypatch.setattr(
            web_fetch, "WebDriverWait", TestEnsureSession._InstantTimeoutWait
        )
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        with pytest.raises(ChessableAuthError):
            with ChessableFetcher():
                pass

        assert fake_browser.quit_called is True
        assert WebFetch.browser is None
