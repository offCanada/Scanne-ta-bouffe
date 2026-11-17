#!/usr/bin/env python3
"""Collecte les trois catégories attribuées sur Aliments du Québec.

Le sitemap public fournit les URL. Chaque fiche est lue une fois.
Les lieux de vente viennent de la section « Trouver ce produit ».
Les formats viennent de « Format disponible ». Une liste vide veut
dire que la fiche ne publie pas cette information.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

SITEMAP_INDEX = "https://alimentsduquebec.com/sitemaps-1-sitemap.xml"
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
USER_AGENT = (
    "Scanne-ta-bouffe/0.1 "
    "(+https://github.com/offCanada/Scanne-ta-bouffe; collecte catalogue public)"
)
CATEGORIES = {
    "nourriture-pour-animaux": "Nourriture pour animaux",
    "poissons-et-fruits-de-mer": "Poissons et fruits de mer",
    "produits-cerealiers": "Produits céréaliers",
}
OUTPUT = Path("data/aliments-du-quebec/produits.json")
WORKERS = 4


def fetch(url: str, timeout: int = 40) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def product_urls() -> list[str]:
    index = ET.fromstring(fetch(SITEMAP_INDEX))
    sitemaps = [
        node.text
        for node in index.findall(".//s:loc", SITEMAP_NS)
        if node.text and "section-products-" in node.text
    ]
    urls: list[str] = []
    seen: set[str] = set()
    for sitemap_url in sitemaps:
        root = ET.fromstring(fetch(sitemap_url))
        for node in root.findall(".//s:loc", SITEMAP_NS):
            url = node.text or ""
            if url in seen or "/aliments-dici/" not in url:
                continue
            slug = url.rstrip("/").split("/aliments-dici/", 1)[1]
            category_slug = slug.split("/", 1)[0]
            if category_slug in CATEGORIES and "/" in slug:
                seen.add(url)
                urls.append(url)
    return urls


def category_of(url: str) -> str:
    slug = url.rstrip("/").split("/aliments-dici/", 1)[1]
    return CATEGORIES[slug.split("/", 1)[0]]


def list_after(html: str, title: str) -> list[str]:
    match = re.search(
        rf'<p class="title">\s*{re.escape(title)}\s*</p>.*?<ul>(.*?)</ul>',
        html,
        re.S,
    )
    if not match:
        return []
    items = []
    for raw in re.findall(r"<li>(.*?)</li>", match.group(1), re.S):
        text = unescape(re.sub(r"<[^>]+>", "", raw))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            items.append(text)
    return items


SKIPPED_HEADINGS = {
    "Produits similaires à découvrir",
    "Envie de découvrir d’autres produits d’ici ?",
    "Laissez-vous inspirer",
}


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = unescape(re.sub(r"<[^>]+>", "", value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def company_heading(html: str) -> str | None:
    for match in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, re.S):
        title = clean(match.group(1))
        if title and title not in SKIPPED_HEADINGS:
            return title
    return None


def parse_product(html: str, url: str) -> dict:
    name = None
    marque = None
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        html,
        re.S,
    )
    if match:
        payload = json.loads(match.group(1))
        for node in payload.get("@graph", []):
            if node.get("@type") != "Product":
                continue
            name = clean(node.get("name"))
            brand = node.get("brand") or {}
            if isinstance(brand, dict):
                marque = clean(brand.get("name"))
            elif isinstance(brand, str):
                marque = clean(brand)
            break
    if not name:
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        name = clean(heading.group(1)) if heading else None
    entreprise = company_heading(html) or marque
    return {
        "nom": name,
        "categorie": category_of(url),
        "entreprise": entreprise,
        "marque": (
            marque
            if marque and marque.casefold() != (entreprise or "").casefold()
            else None
        ),
        "lieux_de_vente": list_after(html, "Trouver ce produit"),
        "formats": list_after(html, "Format disponible"),
        "url": url,
    }


def collect_one(url: str) -> dict:
    last_error = None
    for attempt in range(3):
        try:
            return parse_product(fetch(url), url)
        except Exception as error:  # noqa: BLE001 - retry network and parse errors
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last_error}")


def main() -> None:
    urls = product_urls()
    print(f"{len(urls)} fiches à lire", flush=True)
    products: list[dict] = []
    failures: list[str] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(collect_one, url): url for url in urls}
        for done, future in enumerate(as_completed(futures), start=1):
            url = futures[future]
            try:
                products.append(future.result())
            except Exception as error:  # noqa: BLE001
                failures.append(f"{url} :: {error}")
            if done % 50 == 0 or done == len(urls):
                elapsed = time.time() - started
                print(
                    f"{done}/{len(urls)} en {elapsed:.0f}s, echecs {len(failures)}",
                    flush=True,
                )
    products.sort(key=lambda row: (row["categorie"], row["nom"] or "", row["url"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(products, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"écrit {OUTPUT} ({len(products)} fiches)", flush=True)
    if failures:
        failure_path = OUTPUT.with_name("echecs.json")
        failure_path.write_text(
            json.dumps(failures, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{len(failures)} échecs dans {failure_path}", flush=True)


if __name__ == "__main__":
    main()
