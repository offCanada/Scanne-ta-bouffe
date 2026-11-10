from __future__ import annotations

SOURCE_URL = "https://alimentsduquebec.com/"
SITEMAP_INDEX_URL = f"{SOURCE_URL}sitemaps-1-sitemap.xml"

CATEGORIES: dict[str, tuple[str, str]] = {
    "boulangerie": (
        "Boulangerie, pâtisserie et desserts",
        "boulangerie-patisserie-et-desserts"
    ),
    "collation": (
        "Collation",
        "collation"
    ),
    "confiseries": (
        "Confiseries et produits sucrés",
        "confiseries-et-produits-sucres"
    ),
}
ALL_FOOD_CATEGORIES = tuple(CATEGORIES)

"""Fonctions pour avoir accés au dictionnaire CATEGORIES"""

"""Fonction qui construit url complète vers la catégorie sur le site"""
def category_url(name:str) -> str:
    _,slug = CATEGORIES[name]
    return f"{SOURCE_URL}aliments-dici/{slug}"

"""Fonction qui permet de generer la racine URL pour les fiches de produits d'une catégorie"""
def category_prefix(name:str) -> str:
    return category_url(name) + "/"

"""Fonction qui retourne le nom officiel de la catégorie"""
def display_name(name:str) -> str:
    return CATEGORIES[name][0]