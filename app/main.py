import os
import subprocess
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Price Scraper & Analytics API")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "master_price_data.csv")

def load_data() -> pd.DataFrame:
    """Loads the master price dataset from CSV."""
    if not os.path.exists(CSV_PATH):
        raise HTTPException(status_code=404, detail="Price data master file not found. Run the scraper first.")
    try:
        df = pd.read_csv(CSV_PATH)
        # Ensure correct types
        df['price'] = df['price'].astype(float)
        df['in_stock'] = df['in_stock'].astype(bool)
        return df
    except Exception as e:
        logger.error(f"Error loading CSV data: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading dataset: {str(e)}")

@app.get("/api/stats")
def get_stats():
    """Returns general statistics about the tracked products and shops."""
    df = load_data()
    latest_date = df['date'].max()
    latest_df = df[df['date'] == latest_date]
    
    total_products = latest_df['product_id'].nunique()
    total_shops = latest_df['shop'].nunique()
    
    # Calculate price change (average price shift compared to previous day)
    dates = sorted(df['date'].unique())
    price_change_pct = 0.0
    
    if len(dates) >= 2:
        prev_date = dates[-2]
        prev_df = df[df['date'] == prev_date]
        
        # Average price today vs yesterday for the same products
        avg_today = latest_df[latest_df['price'] > 0]['price'].mean()
        avg_prev = prev_df[prev_df['price'] > 0]['price'].mean()
        
        if avg_prev > 0:
            price_change_pct = ((avg_today - avg_prev) / avg_prev) * 100
            
    return {
        "latest_date": latest_date,
        "total_products": total_products,
        "total_shops": total_shops,
        "price_change_pct": round(price_change_pct, 2),
        "shops": latest_df['shop'].unique().tolist(),
        "brands": latest_df['brand'].unique().tolist()
    }

@app.get("/api/products")
def get_products(brand: Optional[str] = None):
    """
    Returns the latest product variants and their prices across different shops.
    Filters by brand if provided.
    """
    df = load_data()
    latest_date = df['date'].max()
    latest_df = df[df['date'] == latest_date]
    
    if brand:
        latest_df = latest_df[latest_df['brand'].str.lower() == brand.lower()]
        
    products_dict = {}
    
    for _, row in latest_df.iterrows():
        prod_id = row['product_id']
        
        if prod_id not in products_dict:
            products_dict[prod_id] = {
                "product_id": prod_id,
                "title": row['title'],
                "brand": row['brand'],
                "category": row['category'],
                "min_price": float('inf'),
                "max_price": 0.0,
                "in_stock": False,
                "shops": set(),
                "variants": {}
            }
            
        p = products_dict[prod_id]
        p["shops"].add(row['shop'])
        
        # Group variants by RAM and Storage (combining colors in frontend or maintaining them)
        var_key = f"{row['spec_ram']} - {row['spec_storage']}"
        if var_key not in p["variants"]:
            p["variants"][var_key] = {
                "ram": row['spec_ram'],
                "storage": row['spec_storage'],
                "colors": set(),
                "prices": {} # shop_name -> {price, in_stock, url}
            }
            
        v = p["variants"][var_key]
        v["colors"].add(row['spec_color'])
        
        # Add price for this shop (if multiple colors, take the cheapest or in-stock one)
        shop = row['shop']
        price_val = float(row['price'])
        
        # Ignore 0 prices in price range calculation (0 means pre-order / unknown)
        if price_val > 0:
            p["min_price"] = min(p["min_price"], price_val)
            p["max_price"] = max(p["max_price"], price_val)
            
        is_in_stock = bool(row['in_stock'])
        if is_in_stock:
            p["in_stock"] = True
            
        # Record shop details for this variant
        if shop not in v["prices"] or (not v["prices"][shop]["in_stock"] and is_in_stock):
            v["prices"][shop] = {
                "price": price_val,
                "in_stock": is_in_stock,
                "url": row['url']
            }
            
    # Format return list
    formatted_products = []
    for prod_id, p in products_dict.items():
        # Clean up infinite price representation
        if p["min_price"] == float('inf'):
            p["min_price"] = 0.0
            
        p["shops"] = list(p["shops"])
        
        # Format variants dictionary into a list
        variant_list = []
        for v_key, v in p["variants"].items():
            v["colors"] = list(v["colors"])
            # Format prices dictionary into a list
            price_list = []
            for shop_name, shop_details in v["prices"].items():
                price_list.append({
                    "shop": shop_name,
                    "price": shop_details["price"],
                    "in_stock": shop_details["in_stock"],
                    "url": shop_details["url"]
                })
            v["shop_prices"] = price_list
            del v["prices"]
            variant_list.append(v)
            
        p["variants"] = variant_list
        formatted_products.append(p)
        
    return formatted_products

@app.get("/api/trends")
def get_trends(product_id: str, ram: str, storage: str):
    """
    Returns historical price trend data for a specific product and variant.
    """
    df = load_data()
    
    # Filter by product and specifications
    variant_df = df[
        (df['product_id'] == product_id) & 
        (df['spec_ram'].str.lower() == ram.lower()) & 
        (df['spec_storage'].str.lower() == storage.lower())
    ]
    
    if variant_df.empty:
        # Try a relaxed search if exact specs aren't found
        variant_df = df[df['product_id'] == product_id]
        if variant_df.empty:
            raise HTTPException(status_code=404, detail="Product variant not found.")
            
    # Group by date and shop, taking the cheapest price for that date (min price across colors)
    trend_grouped = variant_df.groupby(['date', 'shop'])
    
    trends = {}
    for (date_val, shop_name), group in trend_grouped:
        if shop_name not in trends:
            trends[shop_name] = []
            
        # Get cheapest in-stock price for that day, or just cheapest price
        cheapest_price = group[group['price'] > 0]['price'].min()
        if pd.isna(cheapest_price):
            cheapest_price = group['price'].min()
            
        trends[shop_name].append({
            "date": date_val,
            "price": float(cheapest_price)
        })
        
    # Sort trends for each shop chronologically
    for shop in trends:
        trends[shop] = sorted(trends[shop], key=lambda x: x["date"])
        
    return trends

# Background Task for Scraping
scrape_status = {"status": "idle", "last_run": None, "output": ""}

def run_scraper_task():
    global scrape_status
    scrape_status["status"] = "running"
    scrape_status["output"] = "Starting live scraping task...\n"
    
    try:
        # Run run_scraper.py and capture output
        process = subprocess.Popen(
            ["python", "run_scraper.py"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                scrape_status["output"] += output
                
        rc = process.poll()
        if rc == 0:
            scrape_status["status"] = "success"
            logger.info("Background scraping task finished successfully.")
        else:
            scrape_status["status"] = "failed"
            logger.error(f"Background scraping task failed with return code {rc}")
            
    except Exception as e:
        scrape_status["status"] = "failed"
        scrape_status["output"] += f"\nError executing scraper: {str(e)}"
        logger.error(f"Error in background scraping task: {e}")
        
    scrape_status["last_run"] = datetime.now().isoformat()

@app.post("/api/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    """Triggers a live scrape in a background process."""
    global scrape_status
    if scrape_status["status"] == "running":
        return {"message": "Scraper is already running.", "status": "running"}
        
    background_tasks.add_task(run_scraper_task)
    return {"message": "Scraper task triggered in background.", "status": "running"}

@app.get("/api/scrape/status")
def get_scrape_status():
    """Returns the status and logs of the last scrape execution."""
    return scrape_status

# Serve Frontend static assets
static_path = os.path.join(BASE_DIR, "app", "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
else:
    logger.warning(f"Static files directory not found at {static_path}. Server will only expose the API endpoints.")
