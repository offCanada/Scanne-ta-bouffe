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
    try:
        from scanne_ta_bouffe.scraper import discover_all, scrape_category

        return discover_all, scrape_category
    except ImportError as exc:
        print(f"Erreur lors de l'import du scraper ({exc}).")
        print("Assurez-vous que les dépendances sont installées : uv sync")
        raise SystemExit(1)


def _import_db():
    try:
        from scanne_ta_bouffe.db import build_db, compter_produits, compter_par_categorie

        return build_db, compter_produits, compter_par_categorie
    except ImportError as exc:
        print(f"Erreur lors de l'import de la base ({exc}).")
        print("Assurez-vous que les dépendances sont installées : uv sync")
        raise SystemExit(1)


def cmd_scrape(args: argparse.Namespace) -> int:
    discover_all, scrape_category = _import_scraper()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Une seule lecture du sitemap pour toutes les catégories demandées.
    decouvertes = discover_all(list(args.categories))
    total = 0
    for category in args.categories:
        produits, echecs = scrape_category(
            category, limit=args.limit, delay_s=args.delay, urls=decouvertes.get(category, [])
        )
        out = DATA_DIR / f"{category}.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for produit in produits:
                f.write(json.dumps(produit.to_dict(), ensure_ascii=False) + "\n")
        print(f"[{category}] {len(produits)} produits -> {out} ({len(echecs)} échecs)")
        total += len(produits)
    print(f"Total : {total} produits")
    print("Étape suivante : uv run python main.py build-db")
    return 0

def cmd_build_db(args: argparse.Namespace) -> int:
    build_db, _ , _= _import_db()
    fichiers = sorted(DATA_DIR.glob("*.jsonl"))
    if not fichiers:
        print(f"Aucun JSONL dans {DATA_DIR} — lance d'abord : uv run python main.py scrape --limit 2")
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
    parser = argparse.ArgumentParser(prog="scanne-ta-bouffe", description=__doc__)
    sous = parser.add_subparsers(dest="commande", required=True)

    p_scrape = sous.add_parser("scrape", help="Scraper une ou plusieurs catégories")
    p_scrape.add_argument(
        "--categories",
        nargs="+",
        choices=ALL_FOOD_CATEGORIES,
        default=list(ALL_FOOD_CATEGORIES),
        help="Catégories à scraper (défaut : les 3)",
    )
    p_scrape.add_argument("--limit", type=int, default=None, help="Nombre max de fiches par catégorie (test)")
    p_scrape.add_argument("--delay", type=float, default=0.5, help="Pause entre requêtes, en secondes (défaut 0,5)")
    p_scrape.set_defaults(func=cmd_scrape)

    p_db = sous.add_parser("build-db", help="Reconstruire data/commune.duckdb depuis data/*.jsonl")
    p_db.set_defaults(func=cmd_build_db)

    p_stats = sous.add_parser("stats", help="Compter les produits par catégorie dans la base")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())