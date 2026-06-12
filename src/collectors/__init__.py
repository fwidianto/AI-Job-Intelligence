"""Job Intelligence Platform - Collectors Module

This module contains collectors for various ATS and job board platforms:
- Greenhouse, Lever, SmartRecruiters (API-based)
- Workday, SuccessFactors (enterprise ATS)
- GenericScraper (custom/unknown ATS)
- DynamicScraper (Playwright for JavaScript-rendered pages)
- JobStreet, Glints (job boards)
"""

from .base import BaseCollector, Job, CollectorError
from .factory import CollectorFactory, register_collector
from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .smartrecruiters import SmartRecruitersCollector
from .generic_scraper import GenericScraper, scrape_career_page

# New dynamic scraping modules
from .dynamic_scraper import DynamicScraper, ScrapeResult
from .ats_extractor import WorkdayExtractor, SuccessFactorsExtractor
from .source_resolver import JobSourceResolver, JobSource, ResolverResult, resolve_job_sources

# Job boards
from .job_boards import JobStreetCollector, GlintsCollector

# Register generic scraper as 'custom' collector
CollectorFactory.register('custom', GenericScraper)

__all__ = [
    # Base
    'BaseCollector',
    'Job',
    'CollectorError',
    
    # Factory
    'CollectorFactory',
    'register_collector',
    
    # API-based Collectors
    'GreenhouseCollector',
    'LeverCollector',
    'SmartRecruitersCollector',
    
    # Fallback Collectors
    'GenericScraper',
    'scrape_career_page',
    
    # Dynamic Scraping
    'DynamicScraper',
    'ScrapeResult',
    
    # ATS Extractors
    'WorkdayExtractor',
    'SuccessFactorsExtractor',
    
    # Job Source Resolution
    'JobSourceResolver',
    'JobSource',
    'ResolverResult',
    'resolve_job_sources',
    
    # Job Boards
    'JobStreetCollector',
    'GlintsCollector',
]