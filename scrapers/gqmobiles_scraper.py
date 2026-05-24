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

class GQMobilesScraper(BaseScraper):
    """
    Scraper implementation for GQ Mobiles (gqmobiles.lk)
    Parses headless Next.js state data blocks embedded in the HTML.
    """
    
    @property
    def shop_name(self) -> str:
        return "GQ Mobiles"
        
    @property
    def base_url(self) -> str:
        return "https://gqmobiles.lk"
        
    def _parse_price_range(self, price_str: str) -> Dict[str, float]:
        """
        Parses pricing ranges like "Rs. 139,900.00 - Rs. 199,900.00" or single values.
        """
        # Clean up unicode spaces, HTML tags, or NBSPs
        clean = price_str.replace(r'\u0026nbsp;', ' ').replace('&nbsp;', ' ').replace(',', '')
        nums = re.findall(r'[\d.]+', clean)
        
        if len(nums) >= 2:
            return {"min": float(nums[0]), "max": float(nums[1])}
        elif len(nums) == 1:
            return {"min": float(nums[0]), "max": float(nums[0])}
        return {"min": 0.0, "max": 0.0}

    def _parse_specs_from_title(self, title: str) -> Dict[str, str]:
        """
        Extracts RAM, Storage, and Color specifications from title segments.
        E.g. "Samsung S24 (8GB RAM / 256GB)"
        """
        ram = "Standard"
        storage = "Standard"
        color = "Standard"
        
        # Look for specifications inside parentheses or brackets
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
        return {"ram": ram, "storage": storage, "color": color}

    def scrape(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/collections/smart-phones"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        }
        
        html_content = None
        logger.info(f"Fetching GQ Mobiles: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            html_content = response.text
        except Exception as e:
            logger.warning(f"Standard requests failed for GQ Mobiles ({e}). Trying Playwright fallback...")
            if PLAYWRIGHT_AVAILABLE:
                try:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        context = browser.new_context(user_agent=headers["User-Agent"])
                        page = context.new_page()
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(5000)
                        html_content = page.content()
                        page_title = page.title()
                        browser.close()
                    logger.info(f"Successfully fetched GQ Mobiles using Playwright. Page Title: '{page_title}' | HTML Length: {len(html_content)} | 'in_stock' count: {html_content.count('in_stock')}")
                except Exception as pw_err:
                    logger.error(f"Playwright fallback failed for GQ Mobiles: {pw_err}")
            else:
                logger.warning("Playwright is not available on this system to attempt fallback.")
            
        if not html_content:
            logger.error("Failed to retrieve HTML for GQ Mobiles using both requests and Playwright.")
            return []
        
        # Headless WordPress next state products parsing
        # Looks for the raw JSON nodes containing:
        # "in_stock":true/false,"name":"..."
        pattern = r'"in_stock"\s*:\s*(true|false)\s*,\s*"name"\s*:\s*"([^"]+)"\s*,\s*"onSale"\s*:\s*(true|false)\s*,\s*"price"\s*:\s*"([^"]+)"'
        matches = re.findall(pattern, html_content)
        
        logger.info(f"Found {len(matches)} product entries in GQ Mobiles Next.js payload.")
        
        products_dict = {}
        for m in matches:
            in_stock = m[0] == "true"
            name = m[1].strip()
            price_str = m[3]
            
            # Since Next.js state pushes are repeated inside scripts, deduplicate by name
            if name.lower() in products_dict:
                continue
                
            # Parse price boundaries
            price_limits = self._parse_price_range(price_str)
            min_price = price_limits["min"]
            max_price = price_limits["max"]
            
            # Settle specifications
            specs = self._parse_specs_from_title(name)
            
            # Clean title
            clean_title = re.sub(r'\(.*?\)', '', name).strip()
            brand = "Google" if "pixel" in name.lower() else "Samsung" if "samsung" in name.lower() or " galaxy" in name.lower() or name.startswith("S2") or name.startswith("A3") else "Xiaomi" if "redmi" in name.lower() or "xiaomi" in name.lower() else "Apple" if "iphone" in name.lower() else "Other"
            
            # Slugify standard URL
            slug = name.lower()
            slug = re.sub(r'[^a-z0-9\s\-]', '', slug)
            slug = re.sub(r'[\s\-]+', '-', slug).strip('-')
            product_url = f"{self.base_url}/product/{slug}"
            
            # Binds variants (Minimum price and Maximum price if range, otherwise single variant)
            variants = []
            if min_price > 0:
                variants.append({
                    "id": f"gq_{slug}_min",
                    "price": min_price,
                    "quantity": 5 if in_stock else 0,
                    "in_stock": in_stock,
                    "specifications": specs
                })
                
            if max_price > min_price:
                # Add maximum variant
                variants.append({
                    "id": f"gq_{slug}_max",
                    "price": max_price,
                    "quantity": 5 if in_stock else 0,
                    "in_stock": in_stock,
                    "specifications": specs
                })
                
            if not variants:
                variants.append({
                    "id": f"gq_{slug}_std",
                    "price": 0.0,
                    "quantity": 0,
                    "in_stock": False,
                    "specifications": specs
                })
                
            products_dict[name.lower()] = {
                "title": clean_title,
                "brand": brand,
                "category": "Android",
                "min_price": min_price,
                "max_price": max_price,
                "in_stock": in_stock,
                "url": product_url,
                "variants": variants
            }
            
        final_products = list(products_dict.values())
        logger.info(f"Successfully finished GQ Mobiles crawl, scraping {len(final_products)} total products.")
        return final_products
