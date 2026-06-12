"""
Collector Factory - Automatically creates the correct collector for any career URL

The factory:
1. Accepts a career URL
2. Detects the ATS automatically
3. Returns the appropriate collector instance

No manual ATS assignment required.
"""

import logging
from typing import List, Optional, Dict, Any

from ..detectors.ats_detector import ATSDetector, detect_ats

logger = logging.getLogger(__name__)


class CollectorFactory:
    """
    Factory for creating job collectors based on auto-detected ATS.
    
    Usage:
        collector = CollectorFactory.create(career_url='https://unilever.com/careers')
        jobs = collector.fetch_jobs()
    """
    
    # Registry of collector classes by ATS type
    _collectors = {}
    
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
            Collector instance or None if no collector available
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
        
        # Get the appropriate collector class
        collector_class = cls._collectors.get(ats)
        
        if collector_class:
            try:
                # Handle different collector signatures
                if ats == 'custom':
                    # GenericScraper needs career_url
                    return collector_class(
                        company_name=company_name,
                        career_url=career_url,
                        config=config or {}
                    )
                else:
                    return collector_class(
                        company_name=company_name,
                        company_slug=slug,
                        config=config or {}
                    )
            except Exception as e:
                logger.error("Failed to create %s collector: %s", ats, str(e))
                return None
        
        # Fallback: Use GenericScraper for any unsupported ATS type
        if ats != 'custom':
            generic_class = cls._collectors.get('custom')
            if generic_class:
                try:
                    return generic_class(
                        company_name=company_name,
                        career_url=career_url,
                        config=config or {}
                    )
                except Exception as e:
                    logger.error("Failed to create GenericScraper fallback: %s", str(e))
        
        logger.warning("No collector registered for ATS: %s", ats)
        return None
    
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

# Register collectors
CollectorFactory.register('greenhouse', GreenhouseCollector)
CollectorFactory.register('lever', LeverCollector)
CollectorFactory.register('smartrecruiters', SmartRecruitersCollector)


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