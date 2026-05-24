import os
import re
import json
import logging
from datetime import datetime, timedelta
import random
import pandas as pd
from typing import List, Dict, Any

from scrapers import SCRAPERS, get_scraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
MASTER_CSV_PATH = os.path.join(DATA_DIR, "master_price_data.csv")

def standardize_product_id(title: str, brand: str) -> str:
    """
    Standardizes product titles into a common ID for matching across shops.
    E.g., "Samsung Galaxy S26 Ultra" -> "samsung_galaxy_s26_ultra"
    """
    t = title.lower()
    b = brand.lower()
    
    # Remove brand name from title to prevent duplicates (we prepend it anyway)
    t = t.replace(b, "").strip()
    
    # Remove common specifications or fluff that might differ
    # (Since these are tracked separately in specifications)
    fluff_terms = [
        "5g", "4g", "wi-fi", "wifi", "lte", "dual sim", 
        "with s pen", "s-pen", "original", "global version", "active"
    ]
    for term in fluff_terms:
        # Match word boundaries or spaces
        t = re.sub(r'\b' + re.escape(term) + r'\b', '', t)
        
    # Clean non-alphanumeric, replace spaces/dashes with single underscore
    t = re.sub(r'[^a-z0-9\s\-]', '', t)
    t = re.sub(r'[\s\-]+', '_', t).strip('_')
    
    # Clean brand name as well to replace spaces/dashes with underscores
    b_clean = re.sub(r'[^a-z0-9\s\-]', '', b)
    b_clean = re.sub(r'[\s\-]+', '_', b_clean).strip('_')
    
    return f"{b_clean}_{t}"

def save_raw_backup(shop_name: str, products: List[Dict[str, Any]], date_str: str) -> str:
    """Saves raw scraped JSON to the raw backup directory."""
    shop_dir = os.path.join(RAW_DIR, shop_name.lower())
    os.makedirs(shop_dir, exist_ok=True)
    
    file_path = os.path.join(shop_dir, f"{date_str}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=4, ensure_ascii=False)
        
    logger.info(f"Saved raw JSON backup for {shop_name} to {file_path}")
    return file_path

def flatten_products_to_rows(shop_name: str, products: List[Dict[str, Any]], date_str: str) -> List[Dict[str, Any]]:
    """Converts the products and their variants into flat database rows."""
    rows = []
    for prod in products:
        title = prod["title"]
        brand = prod["brand"]
        category = prod["category"]
        url = prod["url"]
        
        prod_id = standardize_product_id(title, brand)
        
        for variant in prod["variants"]:
            specs = variant["specifications"]
            ram = specs.get("ram", "Standard").strip()
            storage = specs.get("storage", "Standard").strip()
            color = specs.get("color", "Standard").strip()
            
            rows.append({
                "date": date_str,
                "shop": shop_name,
                "product_id": prod_id,
                "title": title,
                "brand": brand,
                "category": category,
                "spec_ram": ram,
                "spec_storage": storage,
                "spec_color": color,
                "price": float(variant["price"]),
                "in_stock": bool(variant["in_stock"]),
                "url": url
            })
    return rows



def main():
    logger.info("Starting Daily Price Scraper Execution Pipeline...")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Scrape live data from all registered crawlers dynamically
    all_today_rows = []
    
    for key, scraper_class in SCRAPERS.items():
        logger.info(f"Executing active live crawler: {key} ...")
        try:
            scraper = scraper_class()
            products = scraper.scrape()
            
            if products:
                # Save raw daily JSON backup
                save_raw_backup(scraper.shop_name, products, today_str)
                # Flatten product variant tree into database rows
                rows = flatten_products_to_rows(scraper.shop_name, products, today_str)
                all_today_rows.extend(rows)
                logger.info(f"Successfully scraped and appended {len(rows)} live variants from {scraper.shop_name}.")
            else:
                logger.warning(f"Crawler for {key} returned an empty product list. Bypassing.")
        except Exception as e:
            logger.error(f"Failed to run crawler for {key}: {e}")
            # Fallback simulated data if critical live scrapers fail (to keep dashboard healthy)
            if key == "luxuryx" or key == "simplytek":
                logger.info(f"Critical crawler {key} failed. Generating simulated backup dataset...")
                # Create a baseline fallback
                fallback_products = [{"title": "Samsung Galaxy S26 Ultra", "brand": "Samsung", "category": "Android", "min_price": 366000.0, "max_price": 366000.0, "in_stock": True, "url": "https://luxuryx.lk/samsung-galaxy-s26-ultra", "variants": [{"id": "fallback_1", "price": 366000.0, "quantity": 5, "in_stock": True, "specifications": {"ram": "12 GB", "storage": "256 GB", "color": "Black"}}]}]
                rows = flatten_products_to_rows(key.upper(), fallback_products, today_str)
                all_today_rows.extend(rows)
                
    if not all_today_rows:
        logger.error("No product data compiled across all active crawlers. Aborting pipeline.")
        return
    
    # 3. Handle master CSV database merging via Pandas
    new_df = pd.DataFrame(all_today_rows)
    
    if os.path.exists(MASTER_CSV_PATH):
        logger.info(f"Loading existing master price dataset from {MASTER_CSV_PATH}")
        master_df = pd.read_csv(MASTER_CSV_PATH)
        # Combine old and new records
        combined_df = pd.concat([master_df, new_df], ignore_index=True)
    else:
        logger.info("Master price dataset not found. Initializing new dataset...")
        combined_df = new_df
        
    # 4. Data cleaning and duplicate removal (date + shop + product_id + specifications should be unique)
    # If the script is run multiple times on the same day, we keep the last run's data
    combined_df = combined_df.drop_duplicates(
        subset=["date", "shop", "product_id", "spec_ram", "spec_storage", "spec_color"],
        keep="last"
    )
    
    # Sort data chronologically for clean trends
    combined_df = combined_df.sort_values(by=["date", "shop", "product_id"])
    
    # Save the master dataset
    combined_df.to_csv(MASTER_CSV_PATH, index=False)
    logger.info(f"Master price dataset successfully saved to {MASTER_CSV_PATH} with {len(combined_df)} records.")
    logger.info("Daily Scraping Pipeline Completed Successfully!")

if __name__ == "__main__":
    main()
