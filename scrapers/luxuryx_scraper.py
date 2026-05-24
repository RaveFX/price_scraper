import re
import json
import logging
import requests
from typing import List, Dict, Any
from scrapers.base_scraper import BaseScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LuxuryXScraper(BaseScraper):
    """
    Scraper implementation for LuxuryX (luxuryx.lk)
    Parses the Alpine.js embedded product definitions in the HTML page.
    """
    
    @property
    def shop_name(self) -> str:
        return "LuxuryX"
        
    @property
    def base_url(self) -> str:
        return "https://luxuryx.lk"
        
    def scrape(self) -> List[Dict[str, Any]]:
        urls = [
            {"url": f"{self.base_url}/android-price", "default_cat": "Android", "default_brand": "Samsung"},
            {"url": f"{self.base_url}/macbook-price-in-sri-lanka", "default_cat": "Macbook", "default_brand": "Apple"}
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        products = []
        for url_info in urls:
            url = url_info["url"]
            default_cat = url_info["default_cat"]
            default_brand = url_info["default_brand"]
            
            logger.info(f"Fetching LuxuryX page: {url}")
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to fetch page from {url}: {e}")
                continue
                
            html_content = response.text
            
            # We look for: productCard(JSON.parse('(JSON_STRING)'))
            # Using a regex to extract the JSON string content inside the JSON.parse('...')
            pattern = r"productCard\(JSON\.parse\('(.*?)'\)\)"
            matches = re.findall(pattern, html_content)
            
            logger.info(f"Found {len(matches)} productCard blocks in the HTML for {url}.")
            
            for i, match in enumerate(matches):
                try:
                    # The string inside x-data is single-quoted, and all internal double-quotes are escaped as \u0022
                    # In python, decoding the unicode escapes is extremely effective
                    # Let's clean up escapes first
                    # The json string has things like \u0022 for quotes and \/ for slashes
                    # Let's decode it safely
                    decoded = match.encode('utf-8').decode('unicode-escape')
                    decoded = decoded.replace(r'\"', '"').replace(r'\\/', '/')
                    
                    raw_prod = json.loads(decoded)
                    
                    # Standardize the product data
                    product_id = raw_prod.get("id")
                    title = raw_prod.get("title", "").strip()
                    brand = raw_prod.get("brand", default_brand).strip()
                    category = raw_prod.get("category", default_cat).strip()
                    slug = raw_prod.get("slug", "")
                    product_url = f"{self.base_url}/{slug}" if slug else url
                    
                    min_price = float(raw_prod.get("min_price", 0))
                    max_price = float(raw_prod.get("max_price", 0))
                    in_stock = bool(raw_prod.get("in_stock", False))
                    
                    variants_list = []
                    for v in raw_prod.get("variants", []):
                        # Clean variant specs
                        specs = v.get("specifications", {})
                        variant_id = v.get("id")
                        
                        variant_price = float(v.get("price", 0))
                        variant_qty = int(v.get("quantity", 0))
                        variant_active = bool(v.get("is_active", True))
                        
                        ram = specs.get("ram", "").strip()
                        storage = specs.get("storage", "").strip()
                        color = specs.get("color", "").strip()
                        
                        variants_list.append({
                          "id": variant_id,
                          "price": variant_price,
                          "quantity": variant_qty,
                          "in_stock": variant_qty > 0 and variant_active,
                          "specifications": {
                              "ram": ram,
                              "storage": storage,
                              "color": color
                          }
                        })
                    
                    # If no variants are listed but there is a product price, let's treat the product itself as a variant
                    if not variants_list:
                        variants_list.append({
                          "id": f"single_{product_id}",
                          "price": min_price,
                          "quantity": 1 if in_stock else 0,
                          "in_stock": in_stock,
                          "specifications": {
                              "ram": "Standard",
                              "storage": "Standard",
                              "color": "Standard"
                          }
                        })
                        
                    products.append({
                      "title": title,
                      "brand": brand,
                      "category": category,
                      "min_price": min_price,
                      "max_price": max_price,
                      "in_stock": in_stock,
                      "url": product_url,
                      "variants": variants_list
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing productCard match {i+1}: {e}")
                    
        logger.info(f"Successfully scraped {len(products)} products from LuxuryX.")
        return products
