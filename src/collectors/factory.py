"""
Collector Factory - Automatically creates the correct collector for any career URL

The factory implements an intelligent fallback pipeline:
1. Try ATS-specific extractor (Workday, SuccessFactors, Greenhouse, Lever, SmartRecruiters)
2. Fallback to GenericScraper for other ATS types
3. Fallback to DynamicScraper (Playwright) for JavaScript-rendered pages
4. Search-based fallback for completely unknown sites

No manual ATS assignment required.
"""

import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from ..detectors.ats_detector import ATSDetector, detect_ats

if TYPE_CHECKING:
    from .base import BaseCollector
    from .dynamic_scraper import DynamicScraper

logger = logging.getLogger(__name__)


class CollectorFactory:
    """
    Factory for creating job collectors based on auto-detected ATS.
    
    Usage:
        collector = CollectorFactory.create(career_url='https://unilever.com/careers')
        jobs = collector.fetch_jobs()
    
    Pipeline:
        1. ATS-specific extractor (Workday, SuccessFactors, Greenhouse, Lever, SmartRecruiters)
        2. GenericScraper for custom/unknown ATS
        3. DynamicScraper (Playwright) for JavaScript-rendered pages
    """
    
    # Registry of collector classes by ATS type
    _collectors = {}
    
    # ATS types that have specialized extractors
    _ATS_EXTRACTORS = {
        'workday': 'ats_extractor.WorkdayExtractor',
        'successfactors': 'ats_extractor.SuccessFactorsExtractor',
    }
    
    @classmethod
    def register(cls, ats_name: str, collector_class):
        """Register a collector class for an ATS type"""
        cls._collectors[ats_name] = collector_class
        logger.debug("Registered collector: %s -> %s", ats_name, collector_class.__name__)
    
    @classmethod
    def create(cls, career_url: str, company_name: str = None, config: Dict = None) -> Optional[Any]:
        """
        Create a collector for the given career URL.
        
        Args:
            career_url: URL of the company career page
            company_name: Optional company name (extracted from URL if not provided)
            config: Optional configuration dict
            
        Returns:
            Collector instance with intelligent fallback
        """
        if not career_url:
            logger.warning("No career URL provided to factory")
            return None
        
        # Auto-detect ATS
        detector = ATSDetector()
        detection = detector.detect(career_url)
        
        ats = detection['ats']
        slug = detection['company_slug'] or company_name or cls._extract_company_from_url(career_url)
        
        logger.info("Factory: Creating collector for %s (ATS: %s)", slug, ats)
        
        # Get company name if not provided
        if not company_name:
            company_name = slug.replace('-', ' ').title() if slug else 'Unknown'
        
        # Build config with all necessary info
        full_config = config or {}
        full_config['ats_type'] = ats
        full_config['company_slug'] = slug
        full_config['api_url'] = detection.get('api_url')
        
        # Try ATS-specific collector first
        collector_class = cls._collectors.get(ats)
        
        if collector_class:
            try:
                if ats == 'custom':
                    return collector_class(
                        company_name=company_name,
                        career_url=career_url,
                        config=full_config
                    )
                else:
                    return collector_class(
                        company_name=company_name,
                        company_slug=slug,
                        config=full_config
                    )
            except Exception as e:
                logger.error("Failed to create %s collector: %s", ats, str(e))
        
        # Fallback: Use GenericScraper for any unsupported ATS type
        if ats != 'custom':
            generic_class = cls._collectors.get('custom')
            if generic_class:
                try:
                    return generic_class(
                        company_name=company_name,
                        career_url=career_url,
                        config=full_config
                    )
                except Exception as e:
                    logger.error("Failed to create GenericScraper fallback: %s", str(e))
        
        logger.warning("No collector registered for ATS: %s", ats)
        return None
    
    @classmethod
    def create_with_fallback(cls, career_url: str, company_name: str = None, 
                            config: Dict = None) -> Optional[Any]:
        """
        Create a collector with full fallback chain including DynamicScraper.
        
        This method ensures at least a DynamicScraper is returned even if
        ATS detection fails or static scraping doesn't work.
        """
        from .dynamic_scraper import DynamicScraper
        
        # Try standard creation first
        collector = cls.create(career_url, company_name, config)
        
        if collector is not None:
            return collector
        
        # Final fallback: DynamicScraper for JavaScript-rendered pages
        logger.info("Using DynamicScraper fallback for: %s", career_url)
        
        if company_name is None:
            from urllib.parse import urlparse
            company_name = urlparse(career_url).netloc.split('.')[0]
        
        # Return a wrapped DynamicScraper as a collector
        return DynamicScraperCollector(career_url, company_name, config or {})
    
    @classmethod
    def create_for_company(cls, company_config: Dict) -> Optional[Any]:
        """
        Create a collector from company configuration dict.
        
        Args:
            company_config: Dict with 'name', 'career_url', 'ats' (optional)
            
        Returns:
            Collector instance or None
        """
        name = company_config.get('name', 'Unknown')
        url = company_config.get('career_url', '')
        
        # Use configured ATS or auto-detect
        ats = company_config.get('ats')
        
        if ats and ats not in ['other', 'manual']:
            # Try to use configured ATS
            collector_class = cls._collectors.get(ats)
            if collector_class:
                slug = company_config.get('slug', cls._extract_company_from_url(url))
                return collector_class(
                    company_name=name,
                    company_slug=slug,
                    config=company_config
                )
        
        # Fall back to auto-detection
        return cls.create(career_url=url, company_name=name, config=company_config)
    
    @classmethod
    def _extract_company_from_url(cls, url: str) -> str:
        """Extract company name from URL"""
        if not url:
            return 'unknown'
        
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        
        # Remove common prefixes
        host = host.replace('www.', '').replace('careers.', '').replace('jobs.', '')
        
        # Remove TLD
        parts = host.split('.')
        if len(parts) > 0:
            return parts[0]
        
        return host
    
    @classmethod
    def get_supported_ats(cls) -> List[str]:
        """Get list of supported ATS types"""
        return list(cls._collectors.keys())


def register_collector(ats_name: str):
    """Decorator to register a collector class"""
    def decorator(cls):
        CollectorFactory.register(ats_name, cls)
        return cls
    return decorator


# Import and register all collectors
from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .smartrecruiters import SmartRecruitersCollector
from .dynamic_scraper import DynamicScraper, ScrapeResult

# Register collectors
CollectorFactory.register('greenhouse', GreenhouseCollector)
CollectorFactory.register('lever', LeverCollector)
CollectorFactory.register('smartrecruiters', SmartRecruitersCollector)


class DynamicScraperCollector:
    """
    Wrapper to use DynamicScraper as a standard collector.
    
    This allows Playwright-based scraping through the same interface
    as other collectors.
    """
    
    ATS_NAME = "dynamic"
    
    def __init__(self, career_url: str, company_name: str, config: Dict = None):
        self.career_url = career_url
        self.company_name = company_name
        self.config = config or {}
        self._scraper = DynamicScraper(timeout=30000, headless=True)
    
    @property
    def company_slug(self) -> str:
        from urllib.parse import urlparse
        return urlparse(self.career_url).netloc.split('.')[0]
    
    def fetch_jobs(self) -> List:
        """Fetch jobs using Playwright dynamic scraping"""
        result = self._scraper.scrape(self.career_url, self.company_name)
        
        if result.success:
            return result.jobs
        
        # Log error but return empty list
        logger.warning(f"DynamicScraper returned no jobs for {self.company_name}: {result.error}")
        return []
    
    def close(self):
        """Clean up resources"""
        self._scraper.close()


if __name__ == "__main__":
    # Test factory
    print("=" * 60)
    print("COLLECTOR FACTORY TEST")
    print("=" * 60)
    
    test_urls = [
        ('https://www.unilever.com/careers/', 'Unilever'),
        ('https://grab.com/careers/', 'Grab'),
        ('https://www.dhl.com/en/careers.html', 'DHL'),
    ]
    
    for url, expected in test_urls:
        collector = CollectorFactory.create(url, expected)
        if collector:
            print(f"\n[OK] {expected}: {type(collector).__name__}")
            print(f"    ATS: {collector.ATS_NAME}")
            print(f"    Slug: {collector.company_slug}")
        else:
            print(f"\n[FAIL] {expected}: No collector available")