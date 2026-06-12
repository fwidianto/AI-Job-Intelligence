"""Job Intelligence Platform - Collectors Module"""

from .base import BaseCollector, Job, CollectorError
from .factory import CollectorFactory, register_collector
from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .smartrecruiters import SmartRecruitersCollector
from .generic_scraper import GenericScraper, scrape_career_page

# Register generic scraper as 'custom' collector
CollectorFactory.register('custom', GenericScraper)

__all__ = [
    'BaseCollector',
    'Job',
    'CollectorError',
    'GreenhouseCollector',
    'LeverCollector',
    'SmartRecruitersCollector',
    'GenericScraper',
    'scrape_career_page',
    'CollectorFactory',
    'register_collector',
]