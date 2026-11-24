import concurrent.futures
import html as html_mod
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests
from scrapling.parser import Selector



CATEGORIES_A_SCRAPER = [
    "boulangerie-patisserie-et-desserts",
    "collation",
    "confiseries-et-produits-sucres",
]

# Adresse de l'outil Sprig du site c'est elle qui renvoie les pages
URL_SPRIG = "https://alimentsduquebec.com/index.php?p=actions/sprig-core/components/render"


class AlimentsDuQuebecScraper:
    """Scraper des fiches produits d'Aliments du Québec (méthode du POC)."""

    def __init__(self):
        self.journal = logging.getLogger("scraper.alimentsduquebec")
        # Session HTTP réutilisée pour toutes les requêtes
        self.session_http = requests.Session()
        self.session_http.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        # Fichier qui contiendra la liste de toutes les URL de fiches.
        self.fichier_urls = Path("data/alimentsduquebec_product_urls.json")
        # Fichier qui contiendra les produits scrapés.
        self.fichier_produits = Path("data/alimentsduquebec_products.json")

    # Point d'entrée et lance tout le scraping et retourne la liste des produits.
    def lancer_scraping(self, **kwargs) -> list[dict[str, Any]]:
        collecter_urls = kwargs.get("collecter_urls", True)
        scraper_pages = kwargs.get("scraper_pages", True)

        if collecter_urls or not self.fichier_urls.exists():
            self._collecter_toutes_les_urls()

        if scraper_pages:
            return self._scraper_tous_les_produits()
        return []

    # Collecte les URL de fiches de toutes les catégories et les sauve
    def _collecter_toutes_les_urls(self) -> list[str]:
        toutes_les_urls = set()
        slugs_deja_vus = set()

        for slug_categorie in CATEGORIES_A_SCRAPER:
            debut_chrono = time.time()
            urls_categorie = self._collecter_urls_categorie(slug_categorie)
            nouveaux_slugs = {url.split("/")[-1] for url in urls_categorie}
            urls_en_commun = len(nouveaux_slugs & slugs_deja_vus)
            slugs_deja_vus.update(nouveaux_slugs)
            toutes_les_urls.update(urls_categorie)
            self.journal.info(
                f"  {slug_categorie}: {len(urls_categorie)} URLs (+{len(urls_categorie) - urls_en_commun} new, "
                f"{urls_en_commun} overlap) in {time.time()-debut_chrono:.0f}s"
            )

        liste_urls_triees = sorted(toutes_les_urls)
        self.fichier_urls.parent.mkdir(parents=True, exist_ok=True)
        with open(self.fichier_urls, "w") as f:
            json.dump(liste_urls_triees, f, indent=2)
        self.journal.info(f"Total unique product URLs: {len(liste_urls_triees)}")
        return liste_urls_triees

    # Collecte les URL de fiches d'UNE catégorie : lit la première page,

    def _collecter_urls_categorie(self, slug_categorie: str) -> list[str]:
        url_categorie = f"https://alimentsduquebec.com/aliments-dici/{slug_categorie}"
        reponse = self.session_http.get(url_categorie, timeout=30)
        if reponse.status_code != 200:
            self.journal.warning(f"  {slug_categorie}: HTTP {reponse.status_code}")
            return []

        config_brute = self._extraire_config_sprig(reponse.text)
        if not config_brute:
            self.journal.warning(f"  {slug_categorie}: no Sprig config found")
            return []

        nombre_total, urls_premiere_page = self._analyser_page_liste(reponse.text, slug_categorie)
        urls = set(urls_premiere_page)

        if nombre_total is None:
            recherche_total = re.search(r"sur\s+([\d,]+)\s", reponse.text)
            if recherche_total:
                nombre_total = int(recherche_total.group(1).replace(",", ""))
            else:
                nombre_total = len(urls) if urls else 12

        nombre_pages = (nombre_total + 11) // 12
        self.journal.info(f"  {slug_categorie}: {nombre_total} products, ~{nombre_pages} pages")

        for numero_page in range(2, nombre_pages + 1):
            urls_page_suivante = self._telecharger_page_sprig(slug_categorie, config_brute, numero_page)
            urls.update(urls_page_suivante)

        return sorted(urls)

    # Extrait la configuration Sprig cachée dans la page
    def _extraire_config_sprig(self, html_page: str) -> str | None:
        correspondance = re.search(r'data-hx-vals="([^"]+)"', html_page)
        if not correspondance:
            return None
        texte_brut = html_mod.unescape(correspondance.group(1))
        try:
            donnees = json.loads(texte_brut)
            return donnees.get("sprig:config")
        except json.JSONDecodeError:
            return None

    # Lit une page de liste : récupère les URL de fiches visibles et le
    def _analyser_page_liste(self, html_page: str, slug_categorie: str) -> tuple[int | None, list[str]]:
        urls_trouvees = re.findall(
            rf'href="(https://alimentsduquebec\.com/aliments-dici/{slug_categorie}/[^"]+)"',
            html_page,
        )
        recherche_total = re.search(r"sur\s+([\d,]+)", html_page)
        nombre_total = int(recherche_total.group(1).replace(",", "")) if recherche_total else None
        return nombre_total, list(set(urls_trouvees))

    # Télécharge UNE page suivante de la liste via Sprig
    def _telecharger_page_sprig(self, slug_categorie: str, config_sprig: str, numero_page: int) -> list[str]:
        parametres = {
            "sprig:config": config_sprig,
            "page": numero_page,
            "tab": "products",
        }
        en_tetes = {
            "HX-Request": "true",
            "HX-Target": "listing",
            "HX-Current-URL": f"https://alimentsduquebec.com/aliments-dici/{slug_categorie}",
            "Referer": f"https://alimentsduquebec.com/aliments-dici/{slug_categorie}",
        }
        try:
            reponse = self.session_http.get(URL_SPRIG, params=parametres, headers=en_tetes, timeout=30)
            if reponse.status_code != 200:
                return []
            return list(set(re.findall(
                r'href="(https://alimentsduquebec\.com/aliments-dici/[^"]+)"',
                reponse.text,
            )))
        except Exception:
            return []

    # Scrape toutes les fiches et reprend là où le dernier run s'était
    def _scraper_tous_les_produits(self) -> list[dict[str, Any]]:
        if not self.fichier_urls.exists():
            self.journal.error("No product URLs file. Run with collecter_urls=True first.")
            return []

        with open(self.fichier_urls) as f:
            toutes_les_urls = json.load(f)

        produits_deja_scrapes = {}
        if self.fichier_produits.exists():
            with open(self.fichier_produits) as f:
                for produit in json.load(f):
                    produits_deja_scrapes[produit["url"]] = produit

        urls_restantes = [url for url in toutes_les_urls if url not in produits_deja_scrapes]
        self.journal.info(f"Products: {len(produits_deja_scrapes)} done, {len(urls_restantes)} remaining")

        if not urls_restantes:
            statistiques = {
                "scraped_products": len(produits_deja_scrapes),
                "errors": len(toutes_les_urls) - len(produits_deja_scrapes),
            }
            with open(self.fichier_produits.parent / "scraping_stats.json", "w") as f:
                json.dump(statistiques, f, indent=2)
            return list(produits_deja_scrapes.values())

        debut = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executeur:
            taches = {executeur.submit(self._scraper_un_produit, url): url for url in urls_restantes}
            nombre_traites = len(produits_deja_scrapes)
            for tache in concurrent.futures.as_completed(taches):
                url = taches[tache]
                resultat_produit = tache.result()
                if resultat_produit:
                    produits_deja_scrapes[url] = resultat_produit
                    nombre_traites += 1

                if nombre_traites % 100 == 0:
                    temps_ecoule = time.time() - debut
                    vitesse = nombre_traites / temps_ecoule if temps_ecoule > 0 else 0
                    self.journal.info(
                        f"  {nombre_traites}/{len(toutes_les_urls)} ({vitesse:.1f}/s, "
                        f"ETA: {(len(toutes_les_urls)-nombre_traites)/vitesse:.0f}s)"
                    )
                    with open(self.fichier_produits, "w") as f:
                        json.dump(list(produits_deja_scrapes.values()), f, indent=2)

        with open(self.fichier_produits, "w") as f:
            json.dump(list(produits_deja_scrapes.values()), f, indent=2)

        duree_totale = time.time() - debut
        statistiques = {
            "scraped_products": len(produits_deja_scrapes),
            "errors": len(toutes_les_urls) - len(produits_deja_scrapes),
        }
        with open(self.fichier_produits.parent / "scraping_stats.json", "w") as f:
            json.dump(statistiques, f, indent=2)
        self.journal.info(f"COMPLETE: {len(produits_deja_scrapes)} products in {duree_totale:.0f}s")
        return list(produits_deja_scrapes.values())


    def _scraper_un_produit(self, url_produit: str) -> dict[str, Any] | None:
        try:
            reponse = self.session_http.get(url_produit, timeout=15)
            if reponse.status_code != 200:
                return None
            selecteur = Selector(reponse.text)
            return self._analyser_fiche_produit(selecteur, url_produit)
        except Exception:
            return None

    def _extraire_items_accordeon(self, selecteur: Selector, titre: str) -> list[str]:
        for accordeon in selecteur.css("div.accordion-grid"):
            titres = accordeon.css("p.title")
            if titres and titres[0].get_all_text().strip() == titre:
                puces = accordeon.find_all("li")
                return [puce.get_all_text().strip() for puce in puces if puce.get_all_text().strip()]
        return []


    def _analyser_fiche_produit(self, selecteur: Selector, url_produit: str) -> dict[str, Any] | None:
        scripts_json_ld = selecteur.css('script[type="application/ld+json"]')
        if not scripts_json_ld:
            return None
        try:
            donnees_json = json.loads(scripts_json_ld[0].text)
        except (json.JSONDecodeError, IndexError):
            return None

        graphe = donnees_json.get("@graph", [donnees_json])
        produit_json = None
        for element in graphe:
            if element.get("@type") == "Product":
                produit_json = element
                break
        if not produit_json:
            return None


        categorie = url_produit.split("/aliments-dici/")[1].split("/")[0]
        lieux_de_vente = self._extraire_items_accordeon(selecteur, "Trouver ce produit")
        formats = self._extraire_items_accordeon(selecteur, "Format disponible")

        return {
            "nom": produit_json.get("name"),
            "categorie": categorie,
            "lieux_de_vente": lieux_de_vente,
            "formats": formats,
            "url": url_produit,
        }

    # Ferme la session HTTP. a appeler à la fin du scraping
    def fermer_session(self):
        self.session_http.close()