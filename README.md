# SmartPrice | Price Scraper & Analytics Dashboard

SmartPrice is a premium, modular price scraping and analytics dashboard built using **Python, Pandas, FastAPI, and Vanilla HTML/CSS/JS**. 

It is designed to automatically crawl online stores daily, record item prices and variants (RAM, Storage, Color), parse and structure the historical logs using Pandas, and present a modern, glassmorphic analytics dashboard. The dashboard tracks price trends over time and compares prices side-by-side across different shops to help users make informed purchasing decisions.

---

## 🌟 Key Features

1. **Robust Modular Crawler Architecture**: Built with an abstract base class so adding a new electronics shop is as simple as creating a subclass and registering it.
2. **Alpine.js Embedded Parsing**: The crawler for `luxuryx.lk` dynamically extracts Alpine.js state blocks, ensuring full variant tracking (all combinations of RAM, Storage, and Colors) with maximum reliability.
3. **Pandas Master Compilation**: Standardizes titles, cleans prices, checks availability, and manages historical tracking in a flat CSV dataset, preventing duplicate runs and sorting chronologically.
4. **Premium SPA Dashboard**:
   - **Modern Aesthetics**: Translucent panels with background blurs (glassmorphism), harmonic dark theme color palettes, bright gradients, and delicate hover scaling transitions.
   - **Dynamic Selection Sync**: Select phone specifications (dropdown) and watch price amount tags, in-stock badges, and retailer lists update in real-time.
   - **Chart.js Historical Graphs**: Interactive daily tracking curves with color-matching shop borders and smooth transparent gradient fills under curves.
   - **Pricing Comparative Matrix**: Highlights the cheapest cash price deal, lists availability states, calculates savings, and provides direct shop links.
   - **Scraper Hub Console**: Run the crawling engine instantly from your web dashboard and watch logs stream to a customized Unix terminal window.

---

## 📂 Project Structure

```text
price_scraper/
├── scrapers/                # Web Crawlers Package
│   ├── __init__.py          # Scraper Registry
│   ├── base_scraper.py      # Abstract Scraper Base Class
│   └── luxuryx_scraper.py   # BeautifulSoup Scraper for LuxuryX
├── data/                    # Price Storage Folders
│   ├── raw/                 # Daily raw crawled JSON backups
│   └── master_price_data.csv# Compiled Pandas Master Database
├── app/                     # Web Dashboard Module
│   ├── main.py              # FastAPI Backend Server using Pandas
│   └── static/              # SPA Dashboard Frontend
│       ├── index.html       # Visual dashboard layout and modals
│       ├── style.css        # Glassmorphism dark-theme styles
│       └── app.js           # AJAX, states, filters, and Chart.js
├── run_scraper.py           # Daily pipeline runner
├── requirements.txt         # Project packages list
└── README.md                # Documentation guide
```

---

## 🚀 Getting Started

### 1. Installation
All primary packages are already standard. If setting up on a clean environment:
```bash
pip install -r requirements.txt
```

### 2. Crawl and Populate Data
Run the crawler script. On its first run, it will scrape LuxuryX live, automatically simulate competitor shop prices (*SimplyTek* and *Doctor Mobile*), backfill **14 days of historic data** to bootstrap the trends chart, and compile `data/master_price_data.csv`:
```bash
python run_scraper.py
```

### 3. Launch the Dashboard
Start the FastAPI server:
```bash
python -m uvicorn app.main:app --reload
```
Open your browser and navigate to: **`http://127.0.0.1:8000`**

---

## 📅 Daily Automation & Scheduling

To track accurate price trends, schedule the scraper to execute once every day.

### Windows (Task Scheduler)
1. Search for **Task Scheduler** in the Windows Start menu and open it.
2. Click **Create Basic Task...** in the Actions panel.
3. Enter a Name (e.g., `SmartPriceScraper`) and Description, then click **Next**.
4. Choose **Daily** and set the time you want it to run (e.g., `22:00:00`), then click **Next**.
5. Set the Action to **Start a program**, then click **Next**.
6. In **Program/script**, enter `python` (or the absolute path to your python executable, e.g. `C:\Users\...\AppData\Local\Programs\Python\Python312\python.exe`).
7. In **Add arguments (optional)**, enter the path to the script: `run_scraper.py`.
8. In **Start in (optional)**, enter the absolute path to your project folder: `D:\CODING\price_scraper`.
9. Click **Finish**. Your daily crawl is now automated!

### Linux / macOS (cron)
Add a cron job by opening your crontab:
```bash
crontab -e
```
Add the following line to run the scraper daily at 10 PM (change paths to absolute paths):
```text
0 22 * * * /usr/bin/python3 /absolute/path/to/price_scraper/run_scraper.py >> /absolute/path/to/price_scraper/scraper.log 2>&1
```

---

## 🛠️ Adding New Retailers/Websites

The scraper engine is fully extensible. To add a new store, follow these 3 steps:

### Step 1: Create a Scraper Class
Under the `scrapers/` directory, create a new file (e.g. `scrapers/simplytek_scraper.py`) and extend `BaseScraper`:
```python
from scrapers.base_scraper import BaseScraper
from typing import List, Dict, Any

class SimplyTekScraper(BaseScraper):
    @property
    def shop_name(self) -> str:
        return "SimplyTek"

    @property
    def base_url(self) -> str:
        return "https://simplytek.lk"

    def scrape(self) -> List[Dict[str, Any]]:
        # Implement your parsing logic using BeautifulSoup or requests
        # Return standard product & variant dictionaries
        return [...]
```

### Step 2: Register the Scraper
Open `scrapers/__init__.py`, import your new class, and add it to the `SCRAPERS` registry map:
```python
from scrapers.simplytek_scraper import SimplyTekScraper

SCRAPERS = {
    "luxuryx": LuxuryXScraper,
    "simplytek": SimplyTekScraper  # Added!
}
```

### Step 3: Run
The pipeline runner (`run_scraper.py`) will automatically fetch and execute all registered scrapers, back up their raw files, clean duplicate rows, and integrate them into the master Pandas database. The dashboard comparison tables and trend charts will immediately adapt and display the new shop's live prices!
