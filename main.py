import logging
from pathlib import Path

from scraper import AlimentsDuQuebecScraper


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main():
    scraper = AlimentsDuQuebecScraper()
    try:
        products = scraper.scrape()
    finally:
        scraper.close()

    import duckdb

    db_path = Path("data/alimentsduquebec_products.duckdb")
    connection = duckdb.connect(str(db_path))
    try:
        connection.execute("CREATE OR REPLACE TABLE products AS SELECT * FROM read_json_auto(?)", [
            str(scraper.products_file)
        ])
    finally:
        connection.close()

    print(f"Scraped {len(products)} products")


if __name__ == "__main__":
    main()
