import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/aliments.db")
JSON_PATH = Path("data/tous_les_produits.json")

produits = json.loads(JSON_PATH.read_text(encoding="utf-8"))

con = sqlite3.connect(DB_PATH)
con.execute("DROP TABLE IF EXISTS produits")
con.execute("""
    CREATE TABLE produits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        lieux_de_vente TEXT,
        formats TEXT,
        categorie TEXT,
        url TEXT UNIQUE
    )
""")

for p in produits:
    con.execute(
        "INSERT OR IGNORE INTO produits (nom, lieux_de_vente, formats, categorie, url) VALUES (?, ?, ?, ?, ?)",
        (p["nom"], ", ".join(p["lieux_de_vente"]), ", ".join(p["formats"]), p["categorie"], p["url"]),
    )

con.commit()
print(f"{con.execute('SELECT COUNT(*) FROM produits').fetchone()[0]} produits dans {DB_PATH}")
con.close()

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/aliments.db")
JSON_PATH = Path("data/tous_les_produits.json")

# Créer le dossier data s'il n'existe pas
DB_PATH.parent.mkdir(exist_ok=True)

if not JSON_PATH.exists():
    print(f"Erreur : {JSON_PATH} introuvable. Lance d'abord scraper.py")
    exit(1)

produits = json.loads(JSON_PATH.read_text(encoding="utf-8"))
print(f"Chargement de {len(produits)} produits depuis le JSON")

con = sqlite3.connect(DB_PATH)
con.execute("DROP TABLE IF EXISTS produits")
con.execute("""
    CREATE TABLE produits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        lieux_de_vente TEXT,
        formats TEXT,
        categorie TEXT,
        url TEXT UNIQUE
    )
""")

for p in produits:
    con.execute(
        "INSERT OR IGNORE INTO produits (nom, lieux_de_vente, formats, categorie, url) VALUES (?, ?, ?, ?, ?)",
        (
            p["nom"],
            ", ".join(p["lieux_de_vente"]) if p["lieux_de_vente"] else "",
            ", ".join(p["formats"]) if p["formats"] else "",
            p["categorie"],
            p["url"],
        ),
    )

con.commit()
count = con.execute("SELECT COUNT(*) FROM produits").fetchone()[0]
print(f"{count} produits dans {DB_PATH}")
con.close()