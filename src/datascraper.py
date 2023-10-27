# data_scraper
from httpx import Client
from selectolax.parser import HTMLParser
from playwright.async_api import async_playwright
from typing import Dict, Optional
import json


class NikeProductScraper:
    def __init__(self, url: str):
        self.client = Client()
        self.url = url
        self.page = None
        self.image_url = None
        self.product_name = None
        self.product_category = None
        self.original_price = None
        self.discount_percentage = None
        self.discounted_price = None
        self.colour_shown = None
        self.style = None
        self.product_description = None
        self.sizes = []
        self.detail_image_url = []

    def fetch_page(self) -> HTMLParser:
        # Fetch the web page and parse it using Selectolax
        response = self.client.get(self.url)
        html_text = response.text
        return HTMLParser(html_text)

    @staticmethod
    def get_image_url(parser: HTMLParser) -> Optional[str]:
        # Extract the main product image URL from the parsed HTML
        img_tag = parser.css_first('img#pdp_6up-hero')
        return img_tag.attributes['src'] if img_tag and 'src' in img_tag.attributes else None

    @staticmethod
    async def find_element_async(parser: HTMLParser, tag: str, attrs: Dict[str, str], default: str = '-') -> str:
        # Find and return the text content of an HTML element with specified tag and attributes
        element = parser.css_first(tag, attrs)
        if element:
            return element.text(strip=True).strip()
        else:
            return default

    async def get_url(self) -> str:
        # Return the product URL
        return self.url

    async def get_image(self, parser: HTMLParser) -> None:
        try:
            image_url = self.get_image_url(parser)
            return image_url
        except TimeoutError:
            print(f"Timeout while fetching image for URL: {self.url}")
            return None

    async def get_product_name(self, parser: HTMLParser) -> str:
        # Get the product name
        product_name = await self.find_element_async(parser, 'h1#pdp_product_title', {})
        return product_name

    async def get_product_category(self, parser: HTMLParser) -> str:
        # Get the product category
        product_category = await self.find_element_async(parser, 'h2[data-test="product-sub-title"]', {})
        return product_category

    @staticmethod
    async def get_original_price(parser: HTMLParser) -> None:
        # Get the original product price
        original_price_element = parser.css_first('div[data-test="product-price"]')
        original_price = original_price_element.text(strip=True).replace("Discounted from",
                                                                         "").strip() if original_price_element else None
        return original_price

    async def get_discount_percentage(self, parser: HTMLParser) -> str:
        # Get the discount percentage
        discount_percentage = await self.find_element_async(parser, 'span[data-testid="OfferPercentage"]', {})
        return discount_percentage.replace("off", "").strip() if discount_percentage else None

    async def get_discounted_price(self, parser: HTMLParser) -> str:
        # Get the discounted price
        discounted_price = await self.find_element_async(parser, 'div[data-test="product-price-reduced"]', {})
        return discounted_price

    async def get_colour_shown(self, parser: HTMLParser) -> str:
        # Get the color of the product
        colour_shown = await self.find_element_async(parser, 'li.description-preview__color-description', {})
        return colour_shown.replace("Colour Shown:", "").strip() if colour_shown else None

    async def get_style(self, parser: HTMLParser) -> str:
        # Get the style of the product
        style = await self.find_element_async(parser, 'li.description-preview__style-color', {})
        return style.replace("Style:", "").strip() if style else None

    async def get_product_description(self, parser: HTMLParser) -> str:
        # Get the product description
        product_description = await self.find_element_async(parser, 'div.description-preview p', {})
        return product_description

    @staticmethod
    async def get_reviews_and_rating(parser: HTMLParser) -> dict:
        # Get the JSON data from the <script> tag
        json_script = parser.css_first('script[type="application/ld+json"]')
        if json_script:
            json_data = json_script.text(strip=True)

            # Initialize reviews and rating with default values
            reviews = 0
            rating = 0.0

            # Parse the JSON data
            try:
                data = json.loads(json_data)

                # Check if the JSON data contains 'aggregateRating'
                if 'aggregateRating' in data:
                    if 'reviewCount' in data['aggregateRating']:
                        reviews = int(data['aggregateRating']['reviewCount'])
                    if 'ratingValue' in data['aggregateRating']:
                        rating = float(data['aggregateRating']['ratingValue'])

                return {"reviews": reviews, "rating": rating}

            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON data: {e}")
                return {"reviews": 0, "rating": 0.0}
        else:
            print("No JSON data found on the page")
            return {"reviews": 0, "rating": 0.0}

    async def get_product_Sizes_and_Images(self) -> dict:
        # Get the available product sizes and detail images using Playwright (async)
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            self.page = await browser.new_page()

            max_retries = 2
            for retries in range(max_retries):
                try:
                    await self.page.goto(self.url, timeout=20000)

                    # Extract and return the available product sizes
                    size_elements = await self.page.query_selector_all(
                        '.mt2-sm div:not(:has(input[disabled])) label.css-xf3ahq')
                    sizes = [await element.inner_text() for element in size_elements]

                    # Extract and return the detail images of the product
                    image_elements = await self.page.query_selector_all('[data-testid^="Thumbnail-Img-"]')
                    images = []
                    for index, image_element in enumerate(image_elements):
                        detail_image_url = await image_element.get_attribute("src")
                        images.append(detail_image_url)

                    return {"sizes": sizes, "images": images}
                except TimeoutError:
                    if retries < max_retries - 1:
                        print(f"Retrying... Attempt {retries + 1} of {max_retries}")
                    else:
                        print(f"Page load timed out for URL: {self.url}")
                        return {"sizes": [], "images": "Page load timed out"}
                except Exception as e:
                    print(f"An error occurred: {e}")
                    return {"sizes": [], "images": "An error occurred"}
                finally:
                    if browser:
                        await browser.close()

