import asyncio
from typing import Set, List
from httpx import AsyncClient, TimeoutException, HTTPStatusError, TooManyRedirects, RequestError
from playwright.async_api import async_playwright, TimeoutError, Page
from selectolax.parser import HTMLParser


class InfiniteScrollScraper:
    @staticmethod
    async def scrape_infinite_scroll(page: Page) -> Set[str]:
        all_main_links = set()
        while True:
            prev_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            new_height = await page.evaluate('document.body.scrollHeight')
            if new_height == prev_height:
                break

            # Find and collect product card elements
            product_cards = await page.query_selector_all('.product-card__body')

            # Extract links from product cards
            for card in product_cards:
                product_link_element = await card.query_selector('.product-card__link-overlay')
                product_link = await product_link_element.get_attribute('href')
                all_main_links.add(product_link)
        return all_main_links


class NikeSpider:
    def __init__(self, url: str, timeout_seconds: int, proxy_list_file: str, infinite_scrolling: bool = False) -> None:
        super().__init__()
        self.client = None
        self.url = url
        self.timeout = timeout_seconds
        self.infinite_scrolling = infinite_scrolling
        self.proxy_list = self.load_proxy_list(proxy_list_file)
        self.current_proxy_index = 0

    @staticmethod
    def load_proxy_list(proxy_list_file):
        with open(proxy_list_file, 'r') as file:
            return file.read().splitlines()

    def get_next_proxy(self):
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return proxy

    async def get_all_main_links(self) -> Set[str]:
        async with async_playwright() as p:
            # Initialize Playwright and set up a headless Chromium browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
            await page.set_extra_http_headers({"User-Agent": user_agent})

            try:
                # Set up proxy for the HTTP client
                self.get_next_proxy()

                # Navigate to the specified URL and wait for the page to load
                await page.goto(self.url)
                await page.wait_for_load_state('load', timeout=self.timeout * 1000)

                # Check if the page content contains "Access Denied" message
                page_content = await page.content()
                if "Access Denied" in page_content:
                    # Handle access denied here, for example, raise an exception
                    raise Exception("Access Denied: The website has blocked your access.")

            except TimeoutError:
                print("Please Increase The Timeout")
                await browser.close()
                return set()

            if self.infinite_scrolling:
                all_main_links = await InfiniteScrollScraper.scrape_infinite_scroll(page)
            else:
                # Find and collect product card elements
                product_cards = await page.query_selector_all('.product-card__body')

                all_main_links = set()

                # Extract links from product cards
                for card in product_cards:
                    product_link_element = await card.query_selector('.product-card__link-overlay')
                    product_link = await product_link_element.get_attribute('href')
                    all_main_links.add(product_link)

            await browser.close()

            return all_main_links

    @staticmethod
    async def get_product_variant_links(product_link: str, session: AsyncClient) -> List[str]:
        try:
            # Send an HTTP request to the product link and parse the response
            response = await session.get(product_link, timeout=20000)
            response.raise_for_status()
            parser = HTMLParser(response.text)
            product_variant = parser.css_first('fieldset')
            if product_variant:
                product_variant_links = []
                for link in product_variant.css('a[href]'):
                    variant_href = link.attributes['href']
                    product_variant_links.append(variant_href)
                return product_variant_links
            else:
                return []
        except (TimeoutException, TooManyRedirects, RequestError, HTTPStatusError) as e:
            print(f"Error fetching {product_link}: {e}")
            return []

    async def get_all_product_links(self):
        async with AsyncClient() as session:
            # Get all links from the page (either with or without infinite scrolling)
            all_main_links = await self.get_all_main_links()
            all_product_links = set()
            total_main_links = len(all_main_links)
            successful_links = 0
            failed_links = 0

            # Set the semaphore to control concurrent connections
            semaphore = asyncio.Semaphore(3)

            async def process_link(link: str):
                retries = 3
                for attempt in range(retries):
                    try:
                        async with semaphore:
                            # Get product variant links for each product link
                            product_variant_links = await self.get_product_variant_links(link, session)
                            all_product_links.update(product_variant_links)  # Add variant links
                            nonlocal successful_links
                            successful_links += 1
                            break
                    except (TimeoutException, TooManyRedirects, RequestError, HTTPStatusError) as e:
                        if attempt < retries - 1:
                            print(f"Retrying {link} (attempt {attempt + 1}) after error: {e}")
                            await asyncio.sleep(5)
                        else:
                            print(f"Error fetching {link}: {e}")
                            nonlocal failed_links
                            failed_links += 1

            # Concurrently process all links
            await asyncio.gather(*[process_link(link) for link in all_main_links])

            all_product_links.update(all_main_links)

            # Print all links status
            print(f"Total main links scraped: {total_main_links}")
            print(f"Successful main links to open: {successful_links}")
            print(f"Failed main links to open: {failed_links}")
            print(f"All Product links ({len(all_product_links)}): {all_product_links}")

            return list(all_product_links)
