# Scanne ta bouffe

## Scraping Aliments du Quebec

Commande :

```powershell
uv run python main.py
```

Categories scrapees :

- `fruits-et-legumes`
- `huiles-et-autres-matieres-grasses`
- `mets-prepares`

Résultats :

- Produits scrapes : 2145
- Erreurs : 0

Les produits sont dans `data/alimentsduquebec_products.json`, les statistiques dans `data/scraping_stats.json` et la base DuckDB dans `data/alimentsduquebec_products.duckdb`.
