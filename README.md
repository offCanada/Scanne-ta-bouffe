# Scraping Aliments du Québec

## Description

Script Python permettant de récupérer automatiquement les fiches de produits du site [Aliments du Québec](https://alimentsduquebec.com/).

Le scraper parcourt les catégories sélectionnées, récupère les liens des produits et extrait les informations disponibles sur chaque fiche.

## Catégories scrapées

- `assaisonnements-sauces-et-condiments`
- `boissons`
- `boissons-alcoolisees`

## Données récupérées

Pour chaque produit, les informations suivantes sont extraites :

- `nom` : nom du produit.
- `lieux_vente` : lieux où le produit est vendu.
- `tailles_formats` : formats disponibles.
- `categorie` : catégorie du produit.
- `url` : lien vers la fiche du produit.


## Installation

1. Installer les dépendances du projet :

```bash
uv sync
```

2. Installer le navigateur Chromium utilisé par Playwright :

```bash
uv run playwright install chromium
```

## Exécution

Pour lancer le scraping :

```bash
uv run python main.py
```

## Résultats

- Produits scrapés : à compléter
- Erreurs : 0

## Fichier généré

Le scraping génère une base de données DuckDB :

- `aliments_quebec.duckdb` : contient les produits récupérés et leurs informations.
