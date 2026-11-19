import json
from pathlib import Path

JSON_PATH = Path("data/tous_les_produits.json")
OUT_PATH = Path("data/base_produits.json")

produits = json.loads(JSON_PATH.read_text(encoding="utf-8"))

# Regroupement par catégorie
base = {}
for p in produits:
    cat = p["categorie"]
    base.setdefault(cat, []).append({
        "nom": p["nom"],
        "lieux_de_vente": p["lieux_de_vente"],
        "formats": p["formats"],
        "url": p["url"],
    })

# Ajout d'un résumé
resultat = {
    "total": len(produits),
    "categories": {
        cat: {"nombre": len(items), "produits": items}
        for cat, items in base.items()
    },
}

OUT_PATH.write_text(
    json.dumps(resultat, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"JSON exporté : {OUT_PATH}")
print(f"Total : {resultat['total']} produits")
for cat, info in resultat["categories"].items():
    print(f"  - {cat} : {info['nombre']} produits")