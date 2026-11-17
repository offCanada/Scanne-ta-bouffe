#Scrapper très simple pour le site Aliment du Québec, qui permet de scrapper les catégories sélectionnées

import asyncio # Permet d'exécuter des opérations asynchrones
import re # Permet les expressions regex pour nettoyer les données
from pathlib import Path

# On se sert de DuckDB pour récupérer les données dans un fichier
import duckdb
#permet de naviger un site web, module qui visite le site et copie les informations
from playwright.async_api import async_playwright


# Catégories sélectionnées
CATEGORIES = {"Assaisonnements, sauces et condiments": "https://alimentsduquebec.com/aliments-dici/assaisonnements-sauces-et-condiments",
              "Boissons": "https://alimentsduquebec.com/aliments-dici/boissons",
              "Boissons alcoolisées": "https://alimentsduquebec.com/aliments-dici/boissons-alcoolisees",
              }


#Comme on récupère les fichiers html, sans cette ligne, on récupère les retours à la ligne, les tabulations ect..
def nettoyer(ligne):
    return re.sub(r"\s+", " ", ligne).strip()


# fonction qui permet de récupérer les lignes de texte situées entre deux mots précis, sans garder les doublons ni les lignes vides.
def extraire_liste(lignes, debut, fin):
    try:
        i = lignes.index(debut) + 1
    except ValueError: #si ne trouve pas où commencer ex Trouver ce produit
        return []

    resultat = [] #Contient les informations récupérées
    for ligne in lignes[i:]: # Parcours les lignes à partir de la ligne de début
        if ligne == fin:
            break # Si on atteint la ligne finale ex Format disponible
        if ligne and ligne not in resultat:
            resultat.append(ligne)

    return resultat #On return les information


# Fonction qui permet de nettoyer les formats pour ne garder que des formats valide
def nettoyer_formats(formats):
    motif = r"^(\d+(?:[.,]\d+)?\s*(?:(?:x|×)\s*\d+(?:[.,]\d+)?\s*)?(?:mL|L|g|kg|mg|lbs?|oz|unités?|vrac))(?=\s*$|\s*[-–—])"

    formats_nettoyes = []

    for format in formats:
        resultat = re.match(motif, format.strip(), re.IGNORECASE) #application du regex sur le code, les majuscule et minuscule n'ont pas d'importance

        if resultat:
            valeur = resultat.group(1).strip() # Récupère la partie intéressante enlevé les noms

            if valeur not in formats_nettoyes: #si n'est pas déja dans la liste de format, on l'ajoute
                formats_nettoyes.append(valeur)

    return formats_nettoyes


async def obtenir_liens_categorie(page, nom_categorie, url_categorie):
    print(f"\nCatégorie : {nom_categorie}") #Donne un repaire d'où on est rendu dans les catégories

    await page.goto(url_categorie, wait_until="domcontentloaded", timeout=60000) #Ouvre la page en maximum 60 secondes
    await page.wait_for_timeout(2500)

    prefix = url_categorie.rstrip("/") + "/" #début adresse courriel catégorie courante

    # Charger les produits jusqu'à ce qu'il n'y en ait plus
    while True:
        bouton = page.get_by_text("Voir plus", exact=True) #Le bouton qui nous permet d'avoir plus de produit

        if await bouton.count() == 0 or not await bouton.first.is_visible(): #Vérifie que le bouton est la
            break

        #le code pour récupérer les liens des produits sur le site
        avant = await page.locator("a[href]").evaluate_all( #sélectionne tous les liens
            """(elements, prefix) => 
                new Set(elements.map(a => a.href).filter(h =>
                    h.startsWith(prefix) && h !== location.href
                )).size""",
            prefix #garde seulement les liens avec la catégorie recherché dans l'url ex  https://alimentsduquebec.com/aliments-dici/boissons/ et n'est pas la page où on est en ce moment, le new wet enlève les doublons
        )

        try:
            await bouton.first.click(timeout=10000) #Voir plus

            await page.wait_for_function( #attend que les produits charge
                """({prefix, avant}) =>
                    new Set(
                        [...document.querySelectorAll("a[href]")]
                        .map(a => a.href)
                        .filter(h => h.startsWith(prefix) && h !== location.href)
                    ).size > avant""",
                arg={"prefix": prefix, "avant": avant},
                timeout=15000
            )

            await page.wait_for_timeout(1000)

        except Exception:
            print("  Aucun nouveau produit chargé. Fin du chargement.")
            break

    # Récupérer tous les liens des produits
    liens = await page.locator("a[href]").evaluate_all(
        """(elements, prefix) => [...new Set(elements.map(a => a.href).filter(h =>
            h.startsWith(prefix) && h !== location.href
        ))]""",
        prefix
    )

    print(f"  {len(liens)} fiches trouvées")
    return liens


async def extraire_produit(page, url, categorie):
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(700)

    donnees = await page.evaluate("""() => ({
        nom: document.querySelector('h1')?.innerText?.trim() || '',
        texte: document.body.innerText
    })""")

    lignes = [nettoyer(x) for x in donnees["texte"].splitlines()]
    lignes = [x for x in lignes if x]

    lieux = extraire_liste(lignes, "Trouver ce produit", "Format disponible")

    formats = extraire_liste(lignes, "Format disponible", "Acheter en ligne")
    formats = nettoyer_formats(formats)

    return {
        "nom": nettoyer(donnees["nom"]),
        "lieux_vente": lieux,
        "tailles_formats": formats,
        "categorie": categorie,
        "url": url
    }


async def main():
    tous_les_produits = []

    async with async_playwright() as p:
        navigateur = await p.chromium.launch(headless=True)
        page = await navigateur.new_page(locale="fr-CA")

        for categorie, url_categorie in CATEGORIES.items():
            liens = await obtenir_liens_categorie(page, categorie, url_categorie)

            for numero, url in enumerate(liens, start=1):
                try:
                    produit = await extraire_produit(page, url, categorie)

                    if produit["nom"]:
                        tous_les_produits.append(produit)
                        print(
                            f"  [{numero}/{len(liens)}] {produit['nom']} " #On imprime le produit au terminal pour se donner une idée d'où on est rendu
                        )

                    else:
                        print(f"  [{numero}/{len(liens)}] Fiche ignorée : nom introuvable")

                except Exception as erreur:
                    print(f"  ERREUR pour {url}: {erreur}")

        await navigateur.close()

    # Création de la base de données DuckDB
    connexion = duckdb.connect(str(Path("aliments_quebec.duckdb"))) #Créer le fichier DuckDB avec

    connexion.execute("DROP TABLE IF EXISTS produits") #Recrée la table si elle éxiste déja

    #Créer la table
    connexion.execute("""
                      CREATE TABLE produits (
                                                nom VARCHAR,
                                                lieux_vente VARCHAR[],
                                                tailles_formats VARCHAR[],
                                                categorie VARCHAR,
                                                url VARCHAR
                      )
                      """)

    #Insére dans le fichier DB tous les produits
    for produit in tous_les_produits:
        connexion.execute(
            "INSERT INTO produits VALUES (?, ?, ?, ?, ?)",
            [
                produit["nom"],
                produit["lieux_vente"],
                produit["tailles_formats"],
                produit["categorie"],
                produit["url"]
            ]
        )

    connexion.close()


if __name__ == "__main__":
    asyncio.run(main())