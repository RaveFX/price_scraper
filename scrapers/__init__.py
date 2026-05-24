from scrapers.base_scraper import BaseScraper
from scrapers.luxuryx_scraper import LuxuryXScraper
from scrapers.simplytek_scraper import SimplyTekScraper
from scrapers.gqmobiles_scraper import GQMobilesScraper
from scrapers.lifemobile_scraper import LifeMobileScraper
# from scrapers.smartmobile_scraper import SmartMobileScraper

SCRAPERS = {
    "luxuryx": LuxuryXScraper,
    "simplytek": SimplyTekScraper,
    "gqmobiles": GQMobilesScraper,
    "lifemobile": LifeMobileScraper,
    # "smartmobile": SmartMobileScraper
}

def get_scraper(name: str) -> BaseScraper:
    """
    Returns an instance of the scraper with the given name.
    """
    if name not in SCRAPERS:
        raise ValueError(f"Unknown scraper: {name}")
    return SCRAPERS[name]()
