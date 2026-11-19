"""
Scraper Aliments du Québec : sitemapindex -> fiches produits -> JSON.
Une fonction par catégorie : laitiers, végétariens, viandes.
"""
import argparse
import gzip
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------- CONFIG
BASE_URL = "https://alimentsduquebec.com"
SITEMAP_INDEX = f"{BASE_URL}/sitemaps-1-sitemap.xml"
OUT_DIR = Path(__file__).parent / "data"
DELAY_SECONDS = 0.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (projet scolaire - scraping aliments du quebec)",
    "Accept-Language": "fr",
}

# Libellés réels sur les pages françaises du site
LABELS_STORES = {"trouvez ce produit chez", "où trouver ce produit", "trouver ce produit"}
LABELS_SIZES = {"formats disponibles", "format disponible", "formats", "format"}
ALL_LABELS = LABELS_STORES | LABELS_SIZES

session = requests.Session()
session.headers.update(HEADERS)


# ---------------------------------------------------------------- RÉSEAU
def fetch(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"  ! erreur ({attempt}/{retries}) {url} : {e}")
            time.sleep(2 * attempt)
    return None


# ---------------------------------------------------------------- SITEMAP
def collect_urls(sitemap_url):
    """Lit le sitemapindex, descend dans chaque sous-sitemap, retourne toutes les URLs."""
    r = fetch(sitemap_url)
    if r is None:
        return []

    content = r.content
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)

    root = ET.fromstring(content)
    kind = root.tag.split("}")[-1]
    locs = [e.text.strip() for e in root.findall(".//{*}loc") if e.text]

    if kind == "sitemapindex":
        urls = []
        for loc in locs:
            print(f"Sous-sitemap : {loc}")
            urls.extend(collect_urls(loc))
        return urls
    return locs


def filter_category(urls, category_slug):
    """
    Garde les fiches produits d'une catégorie donnée.
    Structure réelle : /aliments-dici/{categorie}/{slug-produit}
    """
    result = []
    for u in urls:
        parts = [p for p in urlparse(u).path.split("/") if p]
        # On attend exactement : aliments-dici / categorie / produit
        if len(parts) == 3 and parts[0] == "aliments-dici" and parts[1] == category_slug:
            result.append(u)
    return sorted(set(result))


# ---------------------------------------------------------------- PARSING
def items_after_label(soup, labels):
    """Cherche un libellé (ex: 'Formats disponibles') et retourne les éléments <li> qui suivent."""
    label = soup.find(string=lambda s: s and s.strip().lower() in labels)
    if label is None:
        return []
    items = []
    for el in label.find_all_next(True):
        if el.name in ("h1", "h2", "h3"):
            break
        if el.get_text(" ", strip=True).lower() in ALL_LABELS:
            break
        if el.name == "li":
            text = el.get_text(" ", strip=True)
            if text and text not in items:
                items.append(text)
    return items


def parse_product(html, url, category):
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    return {
        "nom": h1.get_text(" ", strip=True) if h1 else None,
        "lieux_de_vente": items_after_label(soup, LABELS_STORES),
        "formats": items_after_label(soup, LABELS_SIZES),
        "categorie": category,
        "url": url,
    }


# ---------------------------------------------------------------- SCRAPING D'UNE CATÉGORIE
def scrape_category(all_urls, category_name, category_slug, limit=None):
    """
    Scrape une catégorie. Retourne la liste des produits.
    category_slug doit correspondre au vrai nom dans l'URL.
    """
    urls = filter_category(all_urls, category_slug)
    if limit:
        urls = urls[:limit]

    print(f"\n=== {category_name} : {len(urls)} produits à scraper ===")
    produits = []

    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url}")
        r = fetch(url)
        if r is None:
            continue
        data = parse_product(r.text, url, category_name)
        if data["nom"]:
            produits.append(data)
        time.sleep(DELAY_SECONDS)

    return produits


# ---------------------------------------------------------------- MAIN
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limiter le nombre de produits par catégorie (pour tester)")
    args = parser.parse_args()

    print("1. Récupération de toutes les URLs depuis le sitemap...")
    all_urls = collect_urls(SITEMAP_INDEX)
    print(f"   -> {len(all_urls)} URLs au total")

    if not all_urls:
        print("Aucune URL trouvée. Vérifie le sitemap.")
        return

    # Les 3 catégories avec leurs VRAIS slugs
    categories = [
        ("produits laitiers", "produits-laitiers-et-substituts"),
        ("viandes", "viandes"),
        ("produits végétariens", "produits-vegetariens"),
    ]

    tous_les_produits = []
    for nom_categorie, slug in categories:
        produits = scrape_category(all_urls, nom_categorie, slug, limit=args.limit)
        tous_les_produits.extend(produits)
        print(f"   -> {len(produits)} produits trouvés pour {nom_categorie}")

    # Sauvegarde JSON
    OUT_DIR.mkdir(exist_ok=True)
    json_path = OUT_DIR / "tous_les_produits.json"
    json_path.write_text(
        json.dumps(tous_les_produits, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n2. JSON sauvegardé : {json_path} ({len(tous_les_produits)} produits)")


if __name__ == "__main__":
    main()