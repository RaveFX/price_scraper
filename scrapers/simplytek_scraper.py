import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from scrapers.base_scraper import BaseScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimplyTekScraper(BaseScraper):
    """
    Scraper implementation for SimplyTek (simplytek.lk)
    Parses Shopify's collection pages page-by-page to handle pagination,
    extracting product variants from the Shopify analytics event blocks.
    """
    
    @property
    def shop_name(self) -> str:
        return "SimplyTek"
        
    @property
    def base_url(self) -> str:
        return "https://www.simplytek.lk"
        
    def _parse_variant_specs(self, title: str) -> Dict[str, str]:
        """
        Parses variant title strings (e.g. "Black / 3GB RAM 64GB ROM") into RAM, Storage, and Color.
        """
        ram = "Standard"
        storage = "Standard"
        color = "Standard"
        
        if not title or title.lower() in ["default title", "default"]:
            return {"ram": ram, "storage": storage, "color": color}
            
        parts = [p.strip() for p in title.split('/')]
        for part in parts:
            # Look for RAM specifications like "3GB RAM" or "12 GB RAM"
            ram_match = re.search(r'(\d+)\s*(?:gb|gig)\s*ram', part, re.I)
            if ram_match:
                ram = f"{ram_match.group(1)} GB"
                continue
                
            # Look for Storage specifications like "64GB ROM", "256 GB", "1 TB"
            storage_match = re.search(r'(\d+)\s*(?:gb|tb|rom)\b', part, re.I)
            if storage_match:
                unit = "TB" if "tb" in part.lower() else "GB"
                storage = f"{storage_match.group(1)} {unit}"
                continue
                
            # Treat other segments as color
            if part:
                color = part
                
        return {"ram": ram, "storage": storage, "color": color}

    def _extract_variants_json(self, html: str) -> Optional[str]:
        """
        Extracts the Shopify productVariants array from analytics scripts using a bracket counter.
        """
        # Look for the productVariants key inside escaped shopify event strings
        keyword = '\\"productVariants\\":'
        pos = html.find(keyword)
        if pos == -1:
            keyword = '"productVariants":'
            pos = html.find(keyword)
        if pos == -1:
            return None
            
        # Locate the opening bracket '['
        bracket_start = html.find('[', pos)
        if bracket_start == -1:
            return None
            
        # Count brackets to pull the correct full JSON list
        bracket_count = 0
        json_str = ""
        for i in range(bracket_start, len(html)):
            char = html[i]
            json_str += char
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    break
                    
        return json_str

    def scrape(self) -> List[Dict[str, Any]]:
        # SimplyTek smartphone category URL
        current_url = f"{self.base_url}/collections/mobile-phones"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        }
        
        products_dict = {}
        page_num = 1
        
        while current_url:
            logger.info(f"Scraping SimplyTek Page {page_num}: {current_url}")
            try:
                response = requests.get(current_url, headers=headers, timeout=30)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to fetch SimplyTek page: {e}")
                break
                
            html_content = response.text
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract the raw Shopify product list from this page
            variants_json_str = self._extract_variants_json(html_content)
            if variants_json_str:
                # Unescape quotes and slashes inside the extracted string
                cleaned_json = variants_json_str.replace('\\"', '"').replace('\\/', '/')
                try:
                    variants_list = json.loads(cleaned_json)
                    logger.info(f"Extracted {len(variants_list)} raw variants on Page {page_num}.")
                    
                    for item in variants_list:
                        prod_data = item.get("product", {})
                        title = prod_data.get("title", "").strip()
                        brand = prod_data.get("vendor", "Xiaomi").strip()
                        # If Shopify vendor lists the shop itself, infer manufacturer from title
                        if brand.lower() in ["simplytek", "simply tek"]:
                            title_lower = title.lower()
                            if "samsung" in title_lower or "galaxy" in title_lower:
                                brand = "Samsung"
                            elif "pixel" in title_lower or "google" in title_lower:
                                brand = "Google"
                            elif "apple" in title_lower or "iphone" in title_lower:
                                brand = "Apple"
                            elif "redmi" in title_lower or "xiaomi" in title_lower:
                                brand = "Xiaomi"
                            elif "oneplus" in title_lower:
                                brand = "OnePlus"
                            elif "infinix" in title_lower:
                                brand = "Infinix"
                            elif "nothing" in title_lower:
                                brand = "Nothing"
                            else:
                                brand = "Other"
                                
                        slug = prod_data.get("url", "")
                        
                        # Standardize URL
                        prod_url = f"{self.base_url}{slug}" if slug else current_url
                        
                        # Generate unique identifier for this product
                        prod_key = title.lower().strip()
                        
                        if prod_key not in products_dict:
                            products_dict[prod_key] = {
                                "title": title,
                                "brand": brand,
                                "category": "Android",  # Default category
                                "min_price": float('inf'),
                                "max_price": 0.0,
                                "in_stock": False,
                                "url": prod_url,
                                "variants": []
                            }
                            
                        p = products_dict[prod_key]
                        
                        # Settle pricing and specs
                        price = float(item.get("price", {}).get("amount", 0))
                        variant_id = item.get("id")
                        variant_title = item.get("title", "")
                        
                        specs = self._parse_variant_specs(variant_title)
                        
                        # Shopify variant lists typically only show basic details.
                        # Since Shopify storefronts hide quantitative stocks for safety,
                        # we assume it is in stock if price is > 0 (or set True by default)
                        is_in_stock = price > 0
                        
                        p["variants"].append({
                            "id": variant_id,
                            "price": price,
                            "quantity": 5 if is_in_stock else 0,
                            "in_stock": is_in_stock,
                            "specifications": specs
                        })
                        
                        # Update overall boundaries
                        if price > 0:
                            p["min_price"] = min(p["min_price"], price)
                            p["max_price"] = max(p["max_price"], price)
                            p["in_stock"] = True
                            
                except Exception as parse_err:
                    logger.error(f"Error parsing Shopify variants list on Page {page_num}: {parse_err}")
            else:
                logger.warning(f"Could not locate Shopify variants script block on Page {page_num}.")
                
            # Handle Pagination: Look for a link tag indicating the next page
            # Shopify themes output: <link rel="next" href="/collections/...&page=X">
            next_link = soup.find('link', rel='next')
            if next_link:
                next_href = next_link.get('href')
                if next_href:
                    # Construct full absolute URL for next loop
                    current_url = f"{self.base_url}{next_href}" if next_href.startswith('/') else next_href
                    page_num += 1
                else:
                    current_url = None
            else:
                logger.info(f"No pagination 'next' link found. Reached last page: {page_num}.")
                current_url = None
                
        # Clean infinite limits of products that have no priced variants
        final_products = []
        for p in products_dict.values():
            if p["min_price"] == float('inf'):
                p["min_price"] = 0.0
            final_products.append(p)
            
        logger.info(f"Successfully finished SimplyTek crawl, scraping {len(final_products)} total products.")
        return final_products
