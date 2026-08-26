#!/usr/bin/env python3
"""
Filename: web_fetch.py
Author: John DeMastri (original) / adapté chess_toolbox
Version: 0.6
Description: Récupération HTML depuis Chessable via Selenium + Firefox.

Deux modes d'utilisation :

1. Mode login (``chessable-start-browser``) : ouvre Firefox avec le profil
   d'automatisation dédié sur la page de login Chessable. L'utilisateur se
   connecte manuellement, puis ferme Firefox. Les cookies sont persistés dans
   FIREFOX_AUTOMATION_PROFILE_DIR. À lancer UNE FOIS avant le premier run.

2. Mode scraping (``extract-chessable``) : Selenium démarre Firefox avec le
   même profil persistant. Les cookies de session sont réutilisés
   automatiquement — Cloudflare les accepte car ils proviennent d'un login
   réel.
"""

import enum
import os
import os.path
import subprocess
import time
from pathlib import Path
from typing import Any, ClassVar

from beartype import beartype
from bs4 import BeautifulSoup, NavigableString, Tag
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from chess_toolbox.config.settings import WindowMode, settings

# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _persistent_profile_dir() -> Path:
    """Retourne le chemin du profil Firefox persistant pour l'automatisation.

    Ce dossier survit entre les runs — c'est là que les cookies de session
    Chessable sont conservés après le login.

    Returns:
        Chemin vers le dossier profil Firefox.
    """
    profile = Path(settings.firefox_automation_profile_dir)
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def _clear_lock_files(profile_dir: str) -> None:
    """Supprime les fichiers de verrou Firefox laissés par un crash précédent.

    Firefox crée ``lock`` et ``.parentlock`` dans le répertoire de profil.
    S'ils persistent après un crash, Firefox refuse de démarrer.

    Args:
        profile_dir: Répertoire du profil Firefox.
    """
    base = Path(profile_dir)
    lock_names = ["lock", ".parentlock"]
    removed = []
    for name in lock_names:
        p = base / name
        if p.exists() or p.is_symlink():
            try:
                p.unlink()
                removed.append(name)
            except OSError as exc:
                print(f"-- Impossible de supprimer le lock {name} : {exc}")
    if removed:
        print(f"-- Lock files supprimés : {', '.join(removed)}")


def _find_geckodriver() -> str | None:
    """Localise GeckoDriver dans l'ordre de priorité.

    1. Variable d'environnement ``GECKODRIVER_PATH``
    2. Retourne None → Selenium Manager le télécharge/localise automatiquement

    Returns:
        Chemin absolu vers geckodriver, ou None si non spécifié.
    """
    explicit = settings.geckodriver_path
    if explicit and Path(explicit).exists():
        return explicit
    return None


def _as_tag(elem: Tag | NavigableString | None, context: str) -> Tag:
    """Force le narrowing d'un résultat bs4 vers un ``Tag``.

    Les méthodes bs4 comme ``.find()`` retournent ``Tag | NavigableString |
    None`` : ce garde-fou centralise la vérification (au lieu de la répéter
    à chaque appel) et donne un message d'erreur clair si le HTML de
    Chessable a changé de structure.

    Args:
        elem: Résultat de ``.find()`` ou assimilé.
        context: Description du nœud attendu, pour le message d'erreur.

    Returns:
        Le même élément, typé ``Tag``.

    Raises:
        ValueError: Si l'élément n'est pas un ``Tag`` (nœud absent ou texte brut).
    """
    if not isinstance(elem, Tag):
        raise ValueError(f"Élément HTML attendu introuvable ou invalide : {context}")
    return elem


def _attr_str(tag: Tag, key: str) -> str:
    """Lit un attribut HTML de type chaîne sur un ``Tag``.

    Args:
        tag: Élément bs4 dont on lit l'attribut.
        key: Nom de l'attribut à lire.

    Returns:
        La valeur de l'attribut sous forme de chaîne.

    Raises:
        ValueError: Si l'attribut est absent ou n'est pas une simple chaîne
            (certains attributs HTML, comme ``class``, sont multi-valués).
    """
    value = tag.get(key)
    if not isinstance(value, str):
        raise ValueError(
            f"Attribut '{key}' introuvable ou multi-valué sur <{tag.name}>"
        )
    return value


class ChessableAuthError(Exception):
    """Session Chessable invalide ou expirée, détectée en preflight ou en run."""


# Titre de la page d'accueil publique de Chessable. Une session expirée (ou
# bloquée par Cloudflare) redirige silencieusement une requête sur
# /course/<id> vers cette page : le HTML est valide et volumineux, mais ne
# contient aucun chapitre. Un fichier déjà en cache AVANT la mise en place de
# la détection par URL (voir _assert_not_redirected et ensure_session
# ci-dessous) peut donc contenir cette page publique : ce garde-fou détecte
# ce cas au moment de la lecture du cache, où aucune navigation live n'a lieu
# et où la comparaison d'URL est donc impossible (voir FIX-cache-html-empoisonne).
PUBLIC_PAGE_TITLE = "Chessable - Where Science Meets Chess"


def _is_public_page(html: str | None) -> bool:
    """Indique si le HTML est la page d'accueil publique au lieu du contenu attendu.

    Args:
        html: HTML reçu, ou None.

    Returns:
        True si la page correspond à l'accueil public (session non authentifiée).
    """
    if not html:
        return False
    return f"<title>{PUBLIC_PAGE_TITLE}</title>" in html


def _assert_not_redirected(browser: webdriver.Firefox, expected_url: str) -> None:
    """Vérifie que la navigation n'a pas été redirigée hors de l'URL demandée.

    Signal primaire de détection d'une session expirée (voir
    SPEC-session-chessable) : indépendant de la langue ou du contenu textuel
    de la page, contrairement à une détection par titre ou par marqueur HTML.

    Args:
        browser: Instance Selenium juste après un ``browser.get(expected_url)``.
        expected_url: URL demandée.

    Raises:
        ChessableAuthError: Si l'URL obtenue diffère de celle demandée.
    """
    if browser.current_url.rstrip("/") != expected_url.rstrip("/"):
        raise ChessableAuthError(
            f"Session Chessable invalide ou expirée : <{expected_url}> a été "
            f"redirigé vers <{browser.current_url}>. Relancez "
            "`uv run chess_toolbox chessable-login` (ou passez --relogin à "
            "extract-chessable) puis réessayez."
        )


def ensure_session() -> None:
    """Vérifie que la session Chessable est valide avant de traiter le moindre cours.

    Navigue vers la page de profil (accessible uniquement en session
    authentifiée) et compare l'URL obtenue à l'URL demandée.

    Note :
        ``dashboard/`` a été écarté comme URL de vérification : c'est une
        route SPA qui conserve la même URL même sans session (constaté
        empiriquement, aucune redirection serveur), ce qui rend la
        comparaison d'URL inopérante sur cette page. ``profile/`` redirige
        bien vers la racine du site en l'absence de session valide.

    Raises:
        RuntimeError: Si appelé hors d'un bloc ``with ChessableFetcher():``.
        ChessableAuthError: Si la session n'est pas valide.
    """
    browser = WebFetch.browser
    if browser is None:
        raise RuntimeError(
            "WebFetch.browser n'est pas initialisé — ensure_session doit "
            "être appelé dans un bloc `with ChessableFetcher():`"
        )
    profile_url = settings.base_chessable_url + "profile/"
    browser.get(profile_url)
    try:
        WebDriverWait(browser, 15).until(
            EC.any_of(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='user-menu']")
                ),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".user-avatar")),
            )
        )
    except Exception:
        time.sleep(2)
    _assert_not_redirected(browser, profile_url)


# ---------------------------------------------------------------------------
# Login interactif (à appeler une seule fois)
# ---------------------------------------------------------------------------


@beartype
def start_automation_browser() -> None:
    """Lance Firefox avec le profil d'automatisation sur la page de login Chessable.

    Ouvre Firefox avec un profil dédié (FIREFOX_AUTOMATION_PROFILE_DIR).
    L'utilisateur se connecte à Chessable dans cette fenêtre, puis ferme
    Firefox. La session est mémorisée dans le profil et réutilisée par le
    scraper sans nouvelle connexion.

    Le profil dédié est séparé du profil Firefox habituel — pas de conflit
    même si Firefox est déjà ouvert.
    """
    profile_dir = str(_persistent_profile_dir())

    candidates = [
        settings.firefox_binary_path,
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Mozilla Firefox/firefox.exe"),
    ]
    firefox = next((c for c in candidates if c and Path(c).exists()), None)
    if not firefox:
        print("Firefox introuvable dans les emplacements standards.")
        print("Définissez FIREFOX_BINARY_PATH dans .env avec le chemin exact.")
        return

    print(f"Lancement de Firefox (profil : {profile_dir})")
    subprocess.Popen(
        [firefox, "-profile", profile_dir, "https://www.chessable.com/login/"],
        creationflags=(
            subprocess.DETACHED_PROCESS
            if hasattr(subprocess, "DETACHED_PROCESS")
            else 0
        ),
    )
    print()
    print("=" * 60)
    print("Firefox ouvert avec le profil d'automatisation.")
    print()
    print("1. Connectez-vous à Chessable dans la fenêtre qui vient")
    print("   de s'ouvrir (une seule fois — la session est mémorisée).")
    print()
    print("2. Fermez Firefox complètement après la connexion.")
    print()
    print("3. Lancez le scraping :")
    print("   uv run chess_toolbox extract-chessable -courses ID")
    print("=" * 60)


@beartype
def login_and_save_cookies(profile_name: str = "Default") -> None:
    """Ouvre Firefox en mode visible et attend la connexion manuelle à Chessable.

    Lance Firefox avec le profil persistant (FIREFOX_AUTOMATION_PROFILE_DIR),
    navigue vers la page de login Chessable, puis attend que l'utilisateur
    se connecte. Dès que la connexion est détectée, ferme Firefox.

    Les cookies sont persistés dans FIREFOX_AUTOMATION_PROFILE_DIR et
    réutilisés automatiquement par les runs suivants.

    Args:
        profile_name: Ignoré pour Firefox, conservé pour compatibilité CLI.
    """
    profile_dir = str(_persistent_profile_dir())
    _clear_lock_files(profile_dir)
    browser = WebFetch._build_browser(profile_dir)

    print("-- Ouverture de Firefox...")
    browser.get("https://www.chessable.com/login/")

    print("=" * 60)
    print("Connectez-vous à Chessable dans la fenêtre qui vient de s'ouvrir.")
    print("Le programme attend automatiquement la fin de la connexion.")
    print("(Si besoin, appuyez sur Ctrl+C ici pour forcer la fermeture.)")
    print("=" * 60)

    try:
        WebDriverWait(browser, timeout=300).until(
            EC.any_of(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='user-menu']")
                ),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".user-avatar")),
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "a[href='/dashboard/']")
                ),
                EC.url_contains("dashboard"),
            )
        )
        print("-- Connexion détectée ! Sauvegarde des cookies...")
    except Exception:
        print("-- Timeout ou interruption — fermeture de Firefox.")

    time.sleep(2)
    browser.quit()
    print(f"-- Session sauvegardée dans : {profile_dir}")
    print("-- Vous pouvez maintenant lancer le script normalement.")


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------


class FetchMode(enum.Enum):
    """Stratégie de récupération HTML depuis Chessable."""

    #: Utilise le cache existant, ne va chercher que le manquant.
    FETCH_NEW = 0
    #: Refetch systématiquement, écrase le cache.
    FETCH_ALL = 1
    #: N'utilise que le cache, ne fait jamais de requête réseau.
    FETCH_NONE = 2


class WebFetch:
    """Point d'accès HTML pour les pages Chessable (cours, chapitres, variations).

    Toutes les méthodes sont des ``classmethod`` : l'état partagé (mode de
    fetch courant, ``doFetch``) vit sur la classe elle-même.
    """

    FETCH_NEW = FetchMode.FETCH_NEW
    FETCH_ALL = FetchMode.FETCH_ALL
    FETCH_NONE = FetchMode.FETCH_NONE
    flagNames: ClassVar[list[str]] = ["update", "all", "none"]

    doFetch: ClassVar[FetchMode] = FetchMode.FETCH_NEW

    browser: ClassVar[webdriver.Firefox | None] = None

    def __init__(self) -> None:
        """Réinitialise le mode de fetch de la classe à ``FETCH_NEW``."""
        WebFetch.doFetch = FetchMode.FETCH_NEW

    @classmethod
    @beartype
    def getCourseDetail(
        cls, courseId: str, profileName: str
    ) -> tuple[BeautifulSoup | None, list[Any]]:
        """Récupère la page HTML d'un cours et la liste de ses chapitres.

        Args:
            courseId: Identifiant du cours Chessable.
            profileName: Profil navigateur à utiliser.

        Returns:
            Tuple ``(page cours, tags chapitre)``. La liste est vide si la
            page n'a pas pu être récupérée.
        """
        bs = WebFetch.getCourseHtml(courseId, profileName)
        if bs is None:
            return None, []
        chapters = WebFetch.getCourseChapters(bs)
        return bs, chapters

    @classmethod
    @beartype
    def getChapterDetail(
        cls, courseId: str, chapterBs: Tag, profileName: str
    ) -> tuple[BeautifulSoup | None, list[Any]]:
        """Récupère la page HTML d'un chapitre et ses variations.

        Args:
            courseId: Identifiant du cours Chessable.
            chapterBs: Tag ``div.chapter`` du chapitre à charger.
            profileName: Profil navigateur à utiliser.

        Returns:
            Tuple ``(page chapitre, tags variation)``.
        """
        href = _attr_str(
            _as_tag(chapterBs.find("a", href=True), "lien du chapitre"), "href"
        )
        tags = href.split("/")
        chapterID = tags[len(tags) - 1]
        bs = WebFetch.getChapterHtml(courseId, chapterID, profileName)
        variations = WebFetch.getChapterVariations(bs)
        return bs, variations

    @classmethod
    @beartype
    def getCourseChapters(cls, bs: BeautifulSoup) -> list[Any]:
        """Liste les tags ``div.chapter`` d'une page cours.

        Args:
            bs: Page HTML du cours.

        Returns:
            Liste des tags chapitre.
        """
        return bs.find_all("div", class_="chapter")

    @classmethod
    @beartype
    def getCourseName(cls, bs: BeautifulSoup | None) -> str:
        """Extrait le nom du cours depuis le ``<title>`` de sa page.

        Args:
            bs: Page HTML du cours, ou None si non disponible.

        Returns:
            Nom du cours, ou un texte de repli si la page est absente.
        """
        if bs is None:
            return "<No Course HTML Available>"
        title = _as_tag(bs.find("title"), "<title> de la page cours")
        return title.text[:-12]

    @classmethod
    @beartype
    def getChapterVariations(cls, bs: BeautifulSoup | None) -> list[Any]:
        """Liste les tags de variation d'une page chapitre.

        Args:
            bs: Page HTML du chapitre, ou None si non disponible.

        Returns:
            Liste des tags variation (vide si ``bs`` est None).
        """
        if bs is None:
            return []
        return bs.find_all("div", class_="variation-card__row--main")

    @classmethod
    @beartype
    def getChapterName(cls, tag: Tag) -> str:
        """Extrait le titre d'un chapitre depuis son tag.

        Args:
            tag: Tag ``div.chapter``.

        Returns:
            Titre du chapitre.
        """
        title = _as_tag(
            tag.find("div", class_="toBeClamped title"), "titre du chapitre"
        )
        return title.text

    @classmethod
    @beartype
    def getVariationDetailFromTag(
        cls, courseId: str, variationBs: Tag, profileName: str
    ) -> list[Any]:
        """Charge le HTML complet d'une variation à partir de son tag résumé.

        Args:
            courseId: Identifiant du cours Chessable.
            variationBs: Tag résumé de la variation (extrait de la page chapitre).
            profileName: Profil navigateur à utiliser.

        Returns:
            Liste ``[page variation, identifiant variation]``.
        """
        link = _as_tag(variationBs.find("a", href=True), "lien de la variation")
        name = link.text
        href = _attr_str(link, "href")
        tags = href.split("/")
        variationID = tags[len(tags) - 2]
        print(f"Getting Variation Detail '{courseId}-{variationID}-{name}'")
        bs = WebFetch.getVariationHtml(variationID, courseId, profileName)
        return [bs, variationID]

    @classmethod
    @beartype
    def getVariationDetailFromId(
        cls, courseId: str, variationID: str, profileName: str
    ) -> list[Any]:
        """Charge le HTML complet d'une variation à partir de son identifiant.

        Args:
            courseId: Identifiant du cours Chessable.
            variationID: Identifiant de la variation.
            profileName: Profil navigateur à utiliser.

        Returns:
            Liste ``[page variation, identifiant variation]``.
        """
        bs = WebFetch.getVariationHtml(variationID, courseId, profileName)
        return [bs, variationID]

    @classmethod
    @beartype
    def getVariationHtml(
        cls, variationId: str, courseId: str, profileName: str
    ) -> BeautifulSoup | None:
        """Récupère (cache ou réseau) la page HTML d'une variation.

        Args:
            variationId: Identifiant de la variation.
            courseId: Identifiant du cours parent (sert d'emplacement de cache).
            profileName: Profil navigateur à utiliser.

        Returns:
            Page HTML de la variation, ou None en cas d'échec.
        """
        return WebFetch.getHtml(
            "variation", variationId, profileName, "course/" + str(courseId), True
        )

    @classmethod
    @beartype
    def getVariationParts(
        cls, variationBs: Tag | None
    ) -> tuple[str, list[Any], list[Any] | None, list[Any] | None, str | None]:
        """Extrait les éléments bruts d'une variation depuis sa page HTML.

        Args:
            variationBs: Page HTML de la variation, ou None si non disponible.

        Returns:
            Tuple ``(nom, éléments de chapitre, coups, terminateurs, FEN de
            départ)``. En cas d'échec de parsing, retourne un tuple de
            valeurs vides/None.
        """
        if variationBs is None:
            return "", [], None, None, None
        try:
            name = _as_tag(
                variationBs.find("div", id="theOpeningTitle"), "titre de la variation"
            ).text
            chapter = _as_tag(
                variationBs.find("div", class_="allOpeningDetails"),
                "détails de la variation",
            ).find_all("li")
            openingMoves = _as_tag(
                variationBs.find("div", id="theOpeningMoves"), "coups de la variation"
            )
            moves = openingMoves.find_all("span", recursive=False)
            term = openingMoves.find_all("div", recursive=False)
            inputFEN = _attr_str(
                _as_tag(variationBs.find("input", id="inputFEN"), "FEN de départ"),
                "value",
            )
            return name, chapter, moves, term, inputFEN
        except Exception:
            print("problem parsing variation parts\n")
            return "", [], None, None, None

    @classmethod
    @beartype
    def getChapterHtml(
        cls, courseId: str, chapterId: str, profileName: str
    ) -> BeautifulSoup | None:
        """Récupère (cache ou réseau) la page HTML d'un chapitre.

        Args:
            courseId: Identifiant du cours parent.
            chapterId: Identifiant du chapitre.
            profileName: Profil navigateur à utiliser.

        Returns:
            Page HTML du chapitre, ou None en cas d'échec.
        """
        return WebFetch.getHtml("course", courseId + "/" + chapterId, profileName)

    @classmethod
    @beartype
    def getCourseHtml(cls, courseId: str, profileName: str) -> BeautifulSoup | None:
        """Récupère (cache ou réseau) la page HTML d'un cours.

        Args:
            courseId: Identifiant du cours.
            profileName: Profil navigateur à utiliser.

        Returns:
            Page HTML du cours, ou None en cas d'échec.
        """
        return WebFetch.getHtml("course", courseId, profileName)

    @classmethod
    @beartype
    def getHtml(
        cls,
        elementType: str,
        elementId: str,
        profileName: str,
        fileroot: str = "",
        isVar: bool = False,
    ) -> BeautifulSoup | None:
        """Récupère du HTML Chessable, depuis le cache local ou le réseau.

        Le comportement dépend de ``WebFetch.doFetch`` :
        ``FETCH_ALL`` refetch toujours, ``FETCH_NEW`` réutilise le cache et
        ne va chercher que le manquant, ``FETCH_NONE`` n'utilise que le cache.

        Args:
            elementType: Type d'élément Chessable (``"course"``, ``"variation"``).
            elementId: Identifiant de l'élément (peut être vide).
            profileName: Profil navigateur à utiliser.
            fileroot: Préfixe de chemin pour le cache (ex: ``"course/<id>"``).
            isVar: Si True, l'élément est une variation (navigation spécifique).

        Returns:
            HTML parsé en ``BeautifulSoup``, ou None en cas d'échec ou de
            session expirée.
        """
        location = elementType
        if elementId != "":
            location += "/" + elementId
        url = settings.base_chessable_url + location
        if fileroot != "":
            location = fileroot + "/" + location

        if WebFetch.doFetch == FetchMode.FETCH_ALL:
            # session invalide -> ChessableAuthError levée par loadHtmlFromWeb,
            # aucun contenu de page publique ne peut donc atteindre ce point
            pageHtml = WebFetch._fetchHtml(url, profileName, isVar)
            WebFetch.writeHtmlToFile(location, pageHtml)
        else:
            pageHtml = WebFetch.loadHtmlFromFile(location)
            if _is_public_page(pageHtml):
                # Cache empoisonné par un run précédent hors session (fichier déjà
                # sur disque, pas de navigation live donc pas de comparaison d'URL
                # possible) : on l'ignore et on refetch plutôt que de le rejouer
                # éternellement — voir FIX-cache-html-empoisonne.
                print(f"-- cache invalide (page publique) pour <{location}> — refetch")
                pageHtml = ""
            # équivalent à `len(pageHtml) == 0`, mais accepte pageHtml: str | None
            # après réaffectation par _fetchHtml() (mypy narrowing)
            if not pageHtml:
                if WebFetch.doFetch == FetchMode.FETCH_NONE:
                    return None
                pageHtml = WebFetch._fetchHtml(url, profileName, isVar)
                WebFetch.writeHtmlToFile(location, pageHtml)

        return None if pageHtml is None else BeautifulSoup(pageHtml, "html.parser")

    @classmethod
    def _fetchHtml(cls, url: str, profileName: str, isVar: bool) -> str | None:
        """Charge une page Chessable via Firefox Selenium.

        Utilise le profil persistant (FIREFOX_AUTOMATION_PROFILE_DIR) qui
        contient les cookies de session Chessable après le login initial.

        Args:
            url: URL à charger.
            profileName: Ignoré pour Firefox, conservé pour compatibilité.
            isVar: Si True, clique sur le bouton de navigation variation.

        Returns:
            HTML de la page, ou None en cas d'échec.
        """
        return WebFetch.loadHtmlFromWeb(url, profileName, isVar)

    @classmethod
    @beartype
    def loadHtmlFromFile(cls, location: str) -> str:
        """Lit une page HTML depuis le cache local.

        Args:
            location: Chemin relatif (sans extension) sous le cache HTML.

        Returns:
            Contenu du fichier, ou chaîne vide si absent du cache.
        """
        path = settings.chessable_html_cache + location + ".html"
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()

    @classmethod
    @beartype
    def writeHtmlToFile(cls, location: str, content: str | None) -> None:
        """Écrit une page HTML dans le cache local.

        Args:
            location: Chemin relatif (sans extension) sous le cache HTML.
            content: Contenu à écrire, ou None si rien n'a été récupéré.
        """
        path = Path(settings.chessable_html_cache + location[: location.rfind("/")])
        path.mkdir(parents=True, exist_ok=True)
        with open(
            settings.chessable_html_cache + location + ".html", "w", encoding="utf-8"
        ) as f:
            if content is None:
                print("-- returned no content from web")
            else:
                f.write(content)

    @classmethod
    def _build_browser(
        cls, profile_dir: str, profile_name: str = ""
    ) -> webdriver.Firefox:
        """Crée une instance Firefox pilotée par Selenium.

        Utilise le profil persistant pour conserver les cookies de session
        Chessable. ``dom.webdriver.enabled`` est désactivé pour éviter la
        détection par Cloudflare Bot Management. Le mode de fenêtre
        (``settings.chessable_window_mode``) contrôle la visibilité : en
        ``HEADLESS``, Firefox démarre sans rendu de fenêtre ; en
        ``OFFSCREEN``, la fenêtre est réelle mais déplacée hors écran après
        sa construction ; en ``VISIBLE``, la fenêtre reste normale.

        Args:
            profile_dir: Chemin vers le dossier de profil Firefox.
            profile_name: Ignoré pour Firefox, conservé pour compatibilité.

        Returns:
            Instance :class:`selenium.webdriver.Firefox` prête à l'emploi.
        """
        options = FirefoxOptions()
        options.add_argument("-profile")
        options.add_argument(profile_dir)

        firefox_binary = settings.firefox_binary_path
        if firefox_binary:
            options.binary_location = firefox_binary

        options.set_preference("dom.webdriver.enabled", False)

        if settings.chessable_window_mode == WindowMode.HEADLESS:
            options.add_argument("--headless")

        geckodriver = _find_geckodriver()
        service = (
            FirefoxService(executable_path=geckodriver)
            if geckodriver
            else FirefoxService()
        )
        browser = webdriver.Firefox(service=service, options=options)
        if settings.chessable_window_mode == WindowMode.OFFSCREEN:
            # Fenêtre réelle (pas de --headless) mais déplacée hors de tout
            # écran physique — évite les particularités de rendu/fingerprint
            # du vrai mode headless tout en restant invisible pour l'utilisateur.
            browser.set_window_position(-32000, -32000)
        return browser

    @classmethod
    @beartype
    def loadHtmlFromWeb(
        cls, url: str, profileName: str, isVar: bool = False
    ) -> str | None:
        """Charge une page Chessable et retourne son HTML.

        Réutilise le navigateur partagé ouvert par ``ChessableFetcher`` pour
        tout le run (``WebFetch.browser``) — aucun nouveau processus Firefox
        n'est lancé ici.

        Args:
            url: URL à charger.
            profileName: Ignoré pour Firefox, conservé pour compatibilité.
            isVar: Si True, clique sur le bouton de navigation variation.

        Returns:
            HTML de la page, ou None en cas d'échec après 3 tentatives.

        Raises:
            RuntimeError: Si appelé hors d'un bloc ``with ChessableFetcher():``.
            ChessableAuthError: Si la navigation est redirigée hors de l'URL
                demandée (session expirée) — pas de nouvelle tentative dans ce
                cas, une session invalide ne se corrige pas en réessayant.
        """
        browser = WebFetch.browser
        if browser is None:
            raise RuntimeError(
                "WebFetch.browser n'est pas initialisé — loadHtmlFromWeb doit "
                "être appelé dans un bloc `with ChessableFetcher():`"
            )

        for retry in range(3):
            try:
                browser.get(url)
                _css = (
                    By.CSS_SELECTOR,
                    "div.chapter, div.variation-card__row--main, div#controls",
                )
                try:
                    WebDriverWait(browser, 15).until(
                        EC.presence_of_element_located(_css)
                    )
                except Exception:
                    time.sleep(2)

                _assert_not_redirected(browser, url)

                if isVar:
                    controls = browser.find_element(By.ID, "controls")
                    buttons = controls.find_elements(By.TAG_NAME, "button")
                    backClass = buttons[1].get_attribute("class") or ""
                    if "myButtonOff" not in backClass:
                        buttons[1].click()
                        time.sleep(1)

                return browser.page_source

            except ChessableAuthError:
                raise
            except Exception as e:
                exc_msg = getattr(e, "msg", None) or (e.args[0] if e.args else repr(e))
                print(
                    f"error in loadHtmlFromWeb for <{url}>"
                    f" on attempt :{retry}: {exc_msg}"
                )

        return None


class ChessableFetcher:
    """Gestionnaire de contexte : un seul navigateur Firefox pour tout le run.

    Construit l'instance Firefox à l'entrée du bloc ``with``, l'expose via
    ``WebFetch.browser`` pour que ``WebFetch.loadHtmlFromWeb`` la réutilise à
    chaque fetch HTML, puis la ferme à la sortie du bloc.
    """

    def __enter__(self) -> "ChessableFetcher":
        """Lance Firefox, l'assigne à ``WebFetch.browser`` et vérifie la session.

        Returns:
            L'instance courante.

        Raises:
            ChessableAuthError: Si la session Chessable n'est pas valide
                (voir ``ensure_session``). Le navigateur est fermé avant que
                l'exception ne se propage.
        """
        profile_dir = str(_persistent_profile_dir())
        _clear_lock_files(profile_dir)
        WebFetch.browser = WebFetch._build_browser(profile_dir)
        try:
            ensure_session()
        except ChessableAuthError:
            WebFetch.browser.quit()
            WebFetch.browser = None
            raise
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Ferme Firefox et remet ``WebFetch.browser`` à None."""
        if WebFetch.browser is not None:
            try:
                WebFetch.browser.quit()
            except Exception:
                pass
            WebFetch.browser = None
