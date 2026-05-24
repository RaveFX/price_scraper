from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseScraper(ABC):
    """
    Abstract base class for all website scrapers.
    Each website to be scraped should implement a subclass of BaseScraper.
    """
    
    @property
    @abstractmethod
    def shop_name(self) -> str:
        """
        Returns the human-readable name of the shop/website.
        """
        pass
        
    @property
    @abstractmethod
    def base_url(self) -> str:
        """
        Returns the base URL of the website.
        """
        pass

    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        Executes the scraping process.
        Returns a list of products, where each product is represented
        as a dictionary with standard fields and specifications.
        
        Expected structure for each dict:
        {
            'title': str,
            'brand': str,
            'category': str,
            'min_price': float,
            'max_price': float,
            'in_stock': bool,
            'url': str,
            'variants': List[Dict[str, Any]]
        }
        
        And each variant in 'variants':
        {
            'id': int or str,
            'price': float,
            'quantity': int,
            'in_stock': bool,
            'specifications': {
                'ram': str,         # e.g., '12 GB'
                'storage': str,     # e.g., '256 GB'
                'color': str        # e.g., 'Cobalt Violet'
            }
        }
        """
        pass
