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
from .source_resolver import JobSourceResolver, JobSource as SourceJobSource, ResolverResult, resolve_job_sources
from .search_discovery import SearchJobDiscovery, SearchResult, search_jobs, search_company_jobs
from .engine import JobIntelligenceEngine, ProfileConfig, PipelineResult, run_job_intelligence
from .network_intercept import NetworkInterceptor, InterceptResult, CapturedAPI, intercept_job_apis
from .company_discovery import CompanyURLDiscovery, DiscoveredSource, DiscoveryResult, discover_company_sources
from .icims_collector import ICimsCollector, fetch_icims_jobs

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
    'ICimsCollector',
    
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
    'SourceJobSource',
    'ResolverResult',
    'resolve_job_sources',
    
    # Search-Based Discovery
    'SearchJobDiscovery',
    'SearchResult',
    'search_jobs',
    'search_company_jobs',
    
    # Job Intelligence Engine
    'JobIntelligenceEngine',
    'ProfileConfig',
    'PipelineResult',
    'run_job_intelligence',
    
    # Network Intercept (v2)
    'NetworkInterceptor',
    'InterceptResult',
    'CapturedAPI',
    'intercept_job_apis',
    
    # Company Discovery (v2)
    'CompanyURLDiscovery',
    'DiscoveredSource',
    'DiscoveryResult',
    'discover_company_sources',
    
    # Job Boards
    'JobStreetCollector',
    'GlintsCollector',
]