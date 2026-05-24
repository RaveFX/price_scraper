import re
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from scrapers.base_scraper import BaseScraper
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LifeMobileScraper(BaseScraper):
    """
    Scraper implementation for Life Mobile (lifemobile.lk)
    Utilizes Playwright to bypass Cloudflare Turnstile security and crawls
    WooCommerce product listings page-by-page.
    """
    
    @property
    def shop_name(self) -> str:
        return "Life Mobile"
        
    @property
    def base_url(self) -> str:
        return "https://lifemobile.lk"
        
    def _parse_price(self, price_str: str) -> float:
        """Cleans price strings like 'Starting Rs.159,500.00' or 'Rs.159,500.00' into floats."""
        clean = price_str.lower().replace("starting", "").replace("rs.", "").replace("rs", "").replace(",", "").strip()
        nums = re.findall(r'[\d.]+', clean)
        return float(nums[0]) if nums else 0.0

    def _parse_specs_from_title(self, title: str) -> Dict[str, str]:
        """
        Parses memory details from title strings like "Infinix Smart 20 4GB RAM 64GB"
        """
        ram = "Standard"
        storage = "Standard"
        color = "Standard"
        
        # Settle RAM
        ram_match = re.search(r'(\d+)\s*(?:gb|gig)\s*ram', title, re.I)
        if ram_match:
            ram = f"{ram_match.group(1)} GB"
            
        # Settle Storage
        storage_match = re.search(r'\b(\d+)\s*(?:gb|tb)\b(?!.*ram)', title, re.I)
        if storage_match:
            unit = "TB" if "tb" in title.lower() else "GB"
            storage = f"{storage_match.group(1)} {unit}"
            
        return {"ram": ram, "storage": storage, "color": color}

    def scrape(self) -> List[Dict[str, Any]]:
        # Settle category URL
        current_url = f"{self.base_url}/product-category/mobile-phones/"
        products_dict = {}
        
        # Max pages limit for Playwright to keep Daily crawls fast
        MAX_PAGES = 3
        page_num = 1
        
        logger.info(f"Launching headless Playwright for Cloudflare-protected shop: {self.shop_name}")
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                while current_url and page_num <= MAX_PAGES:
                    logger.info(f"Crawling Life Mobile Page {page_num}: {current_url}")
                    
                    page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                    html_content = page.content()
                    
                    soup = BeautifulSoup(html_content, 'lxml')
                    
                    # WooCommerce products grid items selector
                    product_items = soup.select("li.product")
                    logger.info(f"Located {len(product_items)} products on Page {page_num}.")
                    
                    for p_item in product_items:
                        # Extract title details
                        title_el = p_item.select_one("h2") or p_item.select_one(".product-title") or p_item.select_one(".woocommerce-loop-product__title")
                        if not title_el:
                            continue
                        raw_title = title_el.text.strip()
                        
                        # Extract single page link
                        link_el = p_item.find("a")
                        product_url = link_el.get("href") if link_el else current_url
                        
                        # Extract pricing LKR
                        price_el = p_item.select_one(".price") or p_item.select_one(".amount")
                        price_val = self._parse_price(price_el.text.strip()) if price_el else 0.0
                        
                        # Stock status check
                        is_in_stock = True
                        badge_el = p_item.select_one(".out-of-stock") or p_item.select_one(".sold-out")
                        if badge_el:
                            is_in_stock = False
                            
                        # Extract specifications
                        specs = self._parse_specs_from_title(raw_title)
                        
                        # Clean title to get standard names
                        # Remove specification details like "4GB RAM 64GB" from title
                        clean_title = re.sub(r'\b\d+\s*(?:gb|gig)\s*ram\b', '', raw_title, flags=re.I)
                        clean_title = re.sub(r'\b\d+\s*(?:gb|tb)\b', '', clean_title, flags=re.I)
                        clean_title = re.sub(r'\s{2,}', ' ', clean_title).strip()
                        
                        brand = "Google" if "pixel" in clean_title.lower() else "Samsung" if "samsung" in clean_title.lower() or "galaxy" in clean_title.lower() else "Xiaomi" if "redmi" in clean_title.lower() or "xiaomi" in clean_title.lower() else "Apple" if "iphone" in clean_title.lower() or "ipad" in clean_title.lower() else "Motorola" if "motorola" in clean_title.lower() or "moto" in clean_title.lower() else "Infinix" if "infinix" in clean_title.lower() else "Other"
                        
                        # Deduplicate by clean name
                        prod_key = clean_title.lower().strip()
                        if prod_key not in products_dict:
                            products_dict[prod_key] = {
                                "title": clean_title,
                                "brand": brand,
                                "category": "Android",
                                "min_price": float('inf'),
                                "max_price": 0.0,
                                "in_stock": False,
                                "url": product_url,
                                "variants": []
                            }
                            
                        prod_entry = products_dict[prod_key]
                        
                        # Add variant
                        variant_slug = re.sub(r'[^a-z0-9]', '', raw_title.lower())[:20]
                        prod_entry["variants"].append({
                            "id": f"life_{variant_slug}",
                            "price": price_val,
                            "quantity": 5 if is_in_stock else 0,
                            "in_stock": is_in_stock,
                            "specifications": specs
                        })
                        
                        if price_val > 0:
                            prod_entry["min_price"] = min(prod_entry["min_price"], price_val)
                            prod_entry["max_price"] = max(prod_entry["max_price"], price_val)
                            if is_in_stock:
                                prod_entry["in_stock"] = True
                                
                    # Loop next page pagination
                    next_link = soup.select_one("a.next") or soup.select_one("a.page-numbers.next")
                    if next_link and page_num < MAX_PAGES:
                        next_href = next_link.get("href")
                        # WooCommerce next link absolute URL
                        current_url = f"{self.base_url}{next_href}" if next_href.startswith('/') else next_href
                        page_num += 1
                    else:
                        current_url = None
                        
                browser.close()
            except Exception as e:
                logger.error(f"Error in Playwright crawler loop: {e}")
                
        # Clean infinite limits of products that have no priced variants
        final_products = []
        for p in products_dict.values():
            if p["min_price"] == float('inf'):
                p["min_price"] = 0.0
            final_products.append(p)
            
        logger.info(f"Successfully finished Life Mobile crawl, scraping {len(final_products)} total products.")
        return final_products
