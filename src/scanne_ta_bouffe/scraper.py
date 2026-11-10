from __future__ import annotations

import json
import re
import time
import urllib.request

from bs4 import BeautifulSoup

from .models import Produit
from .categories import(
    ALL_FOOD_CATEGORIES,
    SITEMAP_INDEX_URL,
    category_prefix,
    category_url
)

USER_AGENT = "Scanne-ta-bouffe/0.1 (+https://github.com/offCanada/Scanne-ta-bouffe)"
TIMEOUT_S = 30

# Télécharge le HTML brut d'une page produit
def fetchProduct(url: str) -> str:
    req = urllib.request.Request(url, headers = {"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")
    
# Fonction qui extrait les elements d'une section accordéon par son titre
def _accordion_items(soup: BeautifulSoup, titre: str) -> list[str]:
    for p in soup.find_all("p", class_="title"):
        if p.get_text(strip=True) == titre:
            bloc = p.find_parent("div", class_="accordion-grid")
            if bloc is None:
                bloc = p.parent
            return [li.get_text(strip=True) for li in bloc.find_all("li") if li.get_text(strip=True)]
    return []

# Fonction qui extrait le schéma JSON-LD de type Product
def _json_ld_product(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            if data.get("@type") == "Product":
                return data
            for node in data.get("@graph", []):
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
        elif isinstance(data, list):
            for node in data:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node

    return {}

# Parse d'une page html et retourne l'objet Produit
def parse_product(html: str, url: str, category: str) -> Produit:
    soup = BeautifulSoup(html, "html.parser")
    ld = _json_ld_product(soup)
    h1 = soup.find("h1")
    nom = h1.get_text(strip=True) if h1 else str(ld.get("name", ""))
    if not nom and soup.title:
        nom = soup.title.get_text(strip=True).split(" | ")[0]

    

    return Produit(
        nom_produit=nom,
        lieux_de_vente=_accordion_items(soup, "Trouver ce produit"),
        taille_format=_accordion_items(soup, "Format disponible"),
        categorie= category,
    )

# Télecharge et parse une fiche de produit en gérant les erreurs
def _fetch_and_parse(args: tuple[str, str, float]) -> Produit | str:
    url, category, delay_s = args
    try:
        if delay_s:
            time.sleep(delay_s)
        return parse_product(fetchProduct(url), url, category)
    except Exception as exc:  # noqa: BLE001 — une fiche ne doit jamais tuer le run
        print(f"[échec fiche] {url} ({type(exc).__name__})")
        return url

def discover_product_urls(category: str) -> list[str]:
    return discover_all([category]).get(category, [])

def discover_all(categories: list[str] | None = None) -> dict[str, list[str]]:
    wanted = set(categories or ALL_FOOD_CATEGORIES)
    prefixes = {cat: category_prefix(cat) for cat in wanted}
    try:
        index_xml = fetchProduct(SITEMAP_INDEX_URL)
        sitemaps = re.findall(r"<loc>([^<]+)</loc>", index_xml)
        product_sitemaps = [u for u in sitemaps if "section-products" in u]
        found: dict[str, set[str]] = {cat: set() for cat in wanted}
        for sitemap_url in product_sitemaps:
            xml = fetchProduct(sitemap_url)
            for url in re.findall(r"<loc>([^<]+)</loc>", xml):
                for cat, prefix in prefixes.items():
                    if url.startswith(prefix):
                        found[cat].add(url)
                        break
        return {cat: sorted(urls) for cat, urls in found.items()}
    except Exception as exc:
        print(f"[découverte] sitemap illisible ({type(exc).__name__}: {exc}) — repli page catégorie")
        return {cat: discover_from_category_page(cat) for cat in wanted}

def discover_from_category_page(category:str) -> list[str]:
    html = fetchProduct(category_url(category))
    soup = BeautifulSoup(html, "html.parser")
    prefix = category_prefix(category)
    return sorted({a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith(prefix)})

def scrape_category(
    category: str,
    *,
    limit: int | None = None,
    delay_s: float = 0.5,
    urls: list[str] | None = None,
    max_workers: int = 4,
    log=print,
) -> tuple[list[Produit], list[str]]:
    from concurrent.futures import ThreadPoolExecutor

    if category not in ALL_FOOD_CATEGORIES:
        raise ValueError(f"Catégorie inconnue : {category!r} (choix : {', '.join(ALL_FOOD_CATEGORIES)})")
    if urls is None:
        urls = discover_product_urls(category)
    log(f"[{category}] {len(urls)} fiches trouvées")
    if limit is not None:
        urls = urls[:limit]
        log(f"[{category}] limite --limit {limit} : {len(urls)} fiches à scraper")

    produits: list[Produit] = []
    echecs: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for i, resultat in enumerate(
            pool.map(_fetch_and_parse, [(u, category, delay_s) for u in urls]), start=1
        ):
            if isinstance(resultat, str):
                echecs.append(resultat)
                log(f"[{category}] échec {i}/{len(urls)} {resultat}")
            else:
                produits.append(resultat)
            if i % 100 == 0:
                log(f"[{category}] {i}/{len(urls)} fiches lues")
    log(f"[{category}] terminé : {len(produits)} produits, {len(echecs)} échecs")
    return produits, echecs  