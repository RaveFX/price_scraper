import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from scrapers.base_scraper import BaseScraper

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartMobileScraper(BaseScraper):
    """
    Scraper implementation for Smart Mobile (smartmobile.lk)
    Crawls OpenCart pages for both Samsung and Google product categories,
    standardizing specs from parenthesized titles.
    """
    
    @property
    def shop_name(self) -> str:
        return "Smart Mobile"
        
    @property
    def base_url(self) -> str:
        return "https://smartmobile.lk"
        
    def _parse_price(self, price_str: str) -> float:
        """Cleans price strings like 'Rs.293,990.00' into floats."""
        clean = price_str.lower().replace("rs.", "").replace("rs", "").replace(",", "").strip()
        nums = re.findall(r'[\d.]+', clean)
        return float(nums[0]) if nums else 0.0

    def _parse_title_specs(self, title: str) -> Dict[str, Any]:
        """
        Extracts specifications and cleans title text from parenthesized models.
        E.g. "Google Pixel 10 Pro (16GB RAM|128GB) Checking Warranty"
        """
        ram = "Standard"
        storage = "Standard"
        color = "Standard"
        
        # Settle specs inside parentheses
        match = re.search(r'\((.*?)\)', title)
        if match:
            spec_str = match.group(1)
            parts = [p.strip() for p in re.split(r'[|/,]', spec_str)]
            for part in parts:
                ram_match = re.search(r'(\d+)\s*(?:gb|gig)\s*ram', part, re.I)
                if ram_match:
                    ram = f"{ram_match.group(1)} GB"
                    continue
                    
                storage_match = re.search(r'(\d+)\s*(?:gb|tb)\b', part, re.I)
                if storage_match:
                    unit = "TB" if "tb" in part.lower() else "GB"
                    storage = f"{storage_match.group(1)} {unit}"
                    continue
            
            # Settle generic numeric groupings like (8GB|256GB) if undefined
            if ram == "Standard" or storage == "Standard":
                gb_matches = re.findall(r'(\d+)\s*(?:gb|tb)\b', spec_str, re.I)
                if len(gb_matches) >= 2:
                    nums = sorted([int(x) for x in gb_matches])
                    ram = f"{nums[0]} GB"
                    storage = f"{nums[1]} GB"
                elif len(gb_matches) == 1:
                    if "ram" in spec_str.lower():
                        ram = f"{gb_matches[0]} GB"
                    else:
                        storage = f"{gb_matches[0]} GB"
                        
        # Clean title text by stripping specifications
        clean_title = re.sub(r'\(.*?\)', '', title).strip()
        
        # Remove trailing fluff terms
        fluff_list = [
            "checking warranty", "company warranty", "dealer warranty", 
            "genuine brand new", "brand new", "international version"
        ]
        for fluff in fluff_list:
            clean_title = re.sub(r'\b' + re.escape(fluff) + r'\b', '', clean_title, flags=re.I).strip()
            
        # Standardize spaces
        clean_title = re.sub(r'\s{2,}', ' ', clean_title).strip()
        
        return {"ram": ram, "storage": storage, "color": color, "clean_title": clean_title}

    def _scrape_category(self, cat_url: str, brand: str) -> List[Dict[str, Any]]:
        """Scrapes OpenCart products from a specific category URL page-by-page."""
        current_url = cat_url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        }
        
        products_dict = {}
        page_num = 1
        
        while current_url:
            logger.info(f"Scraping Smart Mobile Page {page_num}: {current_url}")
            html_content = None
            try:
                response = requests.get(current_url, headers=headers, timeout=15)
                response.raise_for_status()
                html_content = response.text
            except Exception as e:
                logger.warning(f"Standard requests failed for Smart Mobile ({e}). Trying Playwright fallback...")
                if PLAYWRIGHT_AVAILABLE:
                    try:
                        from playwright.sync_api import sync_playwright
                        with sync_playwright() as p:
                            browser = p.chromium.launch(
                                headless=True,
                                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                            )
                            context = browser.new_context(
                                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                                viewport={"width": 1920, "height": 1080},
                                locale="en-US"
                            )
                            page = context.new_page()
                            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                            page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                            page.wait_for_timeout(5000)
                            html_content = page.content()
                            page_title = page.title()
                            browser.close()
                        logger.info(f"Successfully fetched Smart Mobile using Playwright. Page Title: '{page_title}' | HTML Length: {len(html_content)} | '.product-layout' count: {html_content.count('product-layout')} | '.product-thumb' count: {html_content.count('product-thumb')}")
                    except Exception as pw_err:
                        logger.error(f"Playwright fallback failed for Smart Mobile: {pw_err}")
                else:
                    logger.warning("Playwright is not available on this system to attempt fallback.")
            
            if not html_content:
                logger.error("Failed to retrieve HTML for Smart Mobile using both requests and Playwright.")
                break
            soup = BeautifulSoup(html_content, 'lxml')
            
            # OpenCart grid layouts selector
            product_items = soup.select(".product-layout") or soup.select(".product-thumb")
            logger.info(f"Located {len(product_items)} products on Page {page_num}.")
            
            for p_item in product_items:
                title_el = p_item.select_one("h4 a") or p_item.select_one(".name a")
                if not title_el:
                    continue
                    
                raw_title = title_el.text.strip()
                product_url = title_el.get("href") if title_el else current_url
                
                # Settle pricing
                price_el = p_item.select_one(".price-new") or p_item.select_one(".price")
                price_val = self._parse_price(price_el.text.strip()) if price_el else 0.0
                
                # Check specifications
                spec_details = self._parse_title_specs(raw_title)
                clean_title = spec_details["clean_title"]
                
                # Deduplicate by clean name
                prod_key = clean_title.lower().strip()
                if prod_key not in products_dict:
                    products_dict[prod_key] = {
                        "title": clean_title,
                        "brand": brand,
                        "category": "Android",
                        "min_price": float('inf'),
                        "max_price": 0.0,
                        "in_stock": True,  # OpenCart typical default if listed
                        "url": product_url,
                        "variants": []
                    }
                    
                prod_entry = products_dict[prod_key]
                
                variant_slug = re.sub(r'[^a-z0-9]', '', raw_title.lower())[:20]
                prod_entry["variants"].append({
                    "id": f"smart_{variant_slug}",
                    "price": price_val,
                    "quantity": 5 if price_val > 0 else 0,
                    "in_stock": price_val > 0,
                    "specifications": {
                        "ram": spec_details["ram"],
                        "storage": spec_details["storage"],
                        "color": spec_details["color"]
                    }
                })
                
                if price_val > 0:
                    prod_entry["min_price"] = min(prod_entry["min_price"], price_val)
                    prod_entry["max_price"] = max(prod_entry["max_price"], price_val)
                    
            # OpenCart pagination next page matching
            next_page = None
            pagination = soup.select(".pagination a")
            for a in pagination:
                text = a.text.strip()
                # Match arrows indicating next page: >, >>, »
                if ">" in text or "»" in text or "next" in text.lower():
                    next_page = a.get("href")
                    break
                    
            if next_page and page_num < 10:  # Safety boundary
                current_url = next_page
                page_num += 1
            else:
                current_url = None
                
        return list(products_dict.values())

    def scrape(self) -> List[Dict[str, Any]]:
        # smartmobile.lk divides Google and Samsung list pages
        categories = [
            {"url": f"{self.base_url}/samsung-mobile-phone-price-list-sri-lanka", "brand": "Samsung"},
            {"url": f"{self.base_url}/google-mobile-phones-prices-in-sri-lanka", "brand": "Google"}
        ]
        
        all_products = []
        for cat in categories:
            cat_products = self._scrape_category(cat["url"], cat["brand"])
            all_products.extend(cat_products)
            
        # Clean infinite limits of products that have no priced variants
        final_products = []
        for p in all_products:
            if p["min_price"] == float('inf'):
                p["min_price"] = 0.0
            final_products.append(p)
            
        logger.info(f"Successfully finished Smart Mobile crawl, scraping {len(final_products)} total products.")
        return final_products
