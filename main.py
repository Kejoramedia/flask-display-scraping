import asyncio
import os
from src.scrapingresult import ProductScraperHandler


async def main():
    # User input for scraping multi products
    target_url_multi = "https://www.nike.com/id/w/mens-shoes-nik1zy7ok"
    csv_file_name = "Men's Shoes.csv"
    product_count = 535
    timeout_seconds = 10

    # Setting result directory
    project_directory = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_directory)
    result_directory = os.path.join(project_directory, "result")

    if not os.path.exists(result_directory):
        os.makedirs(result_directory)

    result_file_path = os.path.join(result_directory, csv_file_name)

    await ProductScraperHandler.multi_product(target_url_multi, result_file_path, product_count, timeout_seconds)


if __name__ == "__main__":
    asyncio.run(main())
