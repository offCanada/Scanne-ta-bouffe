from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from scanne_ta_bouffe.categories import ALL_FOOD_CATEGORIES

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "commune.duckdb"

def _import_scraper():
    from scanne_ta_bouffe.scraper import discover_all, scrape_category
    return discover_all, scrape_category

def _import_db():
    from scanne_ta_bouffe.db import build_db, compter_produits, compter_par_categorie
    return build_db, compter_produits, compter_par_categorie

def cmd_scrape(args: argparse.Namespace) -> int:
    discover_all, scrape_category = _import_scraper()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    decouvertes = discover_all(list(args.categories))
    total = 0
    for category in args.categories:
        produits, echecs = scrape_category(
            category,
            urls=decouvertes.get(category, []),
            limit=args.limit,
            delay_s=args.delay,
        )
        out = DATA_DIR / f"{category}.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for produit in produits:
                f.write(json.dumps(produit.to_dict(), ensure_ascii=False) + "\n")
        print(f"[{category}] {len(produits)} produits -> {out} ({len(echecs)} échecs)")
        total += len(produits)
    print(f"Total : {total} produits")
    return 0

def cmd_build_db(args: argparse.Namespace) -> int:
    build_db, _, _ = _import_db()
    
    # On cherche les fichiers .json (tes anciens fichiers)
    fichiers = sorted(DATA_DIR.glob("*.json"))
    # On ignore le fichier global pour ne pas doubler les données
    fichiers = [f for f in fichiers if f.name != "tous_les_produits.json"]

    if not fichiers:
        print(f"Aucun JSON dans {DATA_DIR} — lance d'abord le scraping.")
        return 1
        
    compteurs = build_db(fichiers, DB_PATH)
    print(f"Base commune reconstruite : {DB_PATH}")
    for cle, valeur in compteurs.items():
        print(f"  {cle} : {valeur}")
    return 0

def cmd_stats(args: argparse.Namespace) -> int:
    _, _, compter_par_categorie = _import_db()
    if not DB_PATH.exists():
        print(f"Pas de base {DB_PATH} — lance d'abord : uv run python main.py build-db")
        return 1
    for categorie, nombre in compter_par_categorie(DB_PATH):
        print(f"  {categorie or '(sans catégorie)'} : {nombre}")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scanne-ta-bouffe")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_scrape = sous.add_parser("scrape", help="Scraper une ou plusieurs catégories")
    p_scrape.add_argument("--categories", nargs="+", choices=ALL_FOOD_CATEGORIES, default=list(ALL_FOOD_CATEGORIES))
    p_scrape.add_argument("--limit", type=int, default=None)
    p_scrape.add_argument("--delay", type=float, default=0.5)
    p_scrape.set_defaults(func=cmd_scrape)

    p_db = sous.add_parser("build-db", help="Reconstruire data/commune.duckdb depuis data/*.json")
    p_db.set_defaults(func=cmd_build_db)

    p_stats = sous.add_parser("stats", help="Compter les produits par catégorie dans la base")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())