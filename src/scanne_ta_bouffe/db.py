from __future__ import annotations

import json
from pathlib import Path

import duckdb

from .models import Produit, fusionner

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS produits (
    nom_produit VARCHAR,
    lieux_de_vente VARCHAR[],
    taille_format VARCHAR[],
    categorie VARCHAR
)
"""
def load_jsonl(path: Path) -> list[Produit]:
    produits: list[Produit] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                produits.append(Produit.from_dict(json.loads(line)))
    return produits

def build_db(jsonl_files: list[Path], db_path: Path) -> dict[str, int]:
    """Reconstruit la base commune depuis les JSONL. Renvoie les compteurs."""
    produits: list[Produit] = []
    par_fichier: dict[str, int] = {}
    for path in jsonl_files:
        lus = load_jsonl(path)
        par_fichier[path.name] = len(lus)
        produits.extend(lus)

    fusionnes = fusionner(produits)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        con.execute(TABLE_SQL)
        con.executemany(
            "INSERT INTO produits VALUES (?, ?, ?, ?)",
            [
                (
                    p.nom_produit,
                    p.lieux_de_vente,
                    p.taille_format,
                    p.categorie
                )
                for p in fusionnes
            ],
        )
    finally:
        con.close()
    return {
        "lignes_jsonl": len(produits),
        "lignes_apres_fusion": len(fusionnes),
        "doublons_fusionnes": len(produits) - len(fusionnes),
        **{f"fichier_{k}": v for k, v in par_fichier.items()},
    }

def compter_produits(db_path: Path) -> list[tuple[str, int]]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(
            "SELECT count(*) FROM produits"
        ).fetchall()
    finally:
        con.close()

def compter_par_categorie(db_path: Path) -> list[tuple[str, int]]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(
            "SELECT categorie, count(*) FROM produits GROUP BY categorie ORDER BY categorie"
        ).fetchall()
    finally:
        con.close()
