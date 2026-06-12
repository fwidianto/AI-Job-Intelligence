"""
Collector Factory - ATS-Only Job Collection System

⚠️ STRICT RULE: This factory ONLY creates ATS-specific collectors.
NO fallback to HTML scraping, GenericScraper, or any non-ATS method.

Supported ATS types:
- greenhouse: GreenhouseCollector
- lever: LeverCollector
- workday: WorkdayCollector (ONLY if structured endpoint confirmed)
- smartrecruiters: SmartRecruitersCollector
- icims: ICimsCollector

If a source is NOT one of the above → return None (skip company)
"""

import logging
from typing import List, Optional, Dict, Any

from ..detectors.ats_detector import ATSDetector, detect_ats

logger = logging.getLogger(__name__)


class CollectorFactory:
    """
    ATS-Only Factory for creating job collectors.
    
    ⚠️ STRICT MODE: NO FALLBACK SCRAPING
    
    Pipeline:
        1. Receive company name + career URL
        2. Detect ATS type (greenhouse, lever, workday, smartrecruiters, icims)
        3. Route to appropriate collector
        4. If unknown → SKIP (do NOT scrape)
    
    Usage:
        collector = CollectorFactory.create(
            company_name='Grab',
            career_url='https://grab.careers'
        )
        if collector:
            jobs = collector.fetch_jobs()
        else:
            # SKIP company - no ATS match
            pass
    """
    
    # ATS-ONLY supported types
    SUPPORTED_ATS = {
        'greenhouse',
        'lever', 
        'workday',
        'smartrecruiters',
        'icims'
    }
    
    # Registry of collector classes by ATS type
    _collectors = {}
    
    @classmethod
    def register(cls, ats_name: str, collector_class):
        """Register a collector class for an ATS type"""
        if ats_name in cls.SUPPORTED_ATS:
            cls._collectors[ats_name] = collector_class
            logger.debug("Registered ATS collector: %s -> %s", ats_name, collector_class.__name__)
        else:
            logger.warning("Cannot register non-ATS collector: %s", ats_name)
    
    @classmethod
    def create(cls, company_name: str, career_url: str, config: Dict = None) -> Optional[Any]:
        """
        Create a collector for the given company and career URL.
        
        ⚠️ STRICT RULE: Returns None if ATS is not in SUPPORTED_ATS list.
        DO NOT fall back to scraping.
        
        Args:
            company_name: Company name
            career_url: Career page URL
            config: Optional configuration dict
            
        Returns:
            Collector instance OR None (if unsupported ATS)
        """
        if not career_url:
            logger.warning("CollectorFactory: No career URL provided")
            return None
        
        # Detect ATS type
        detector = ATSDetector()
        detection = detector.detect(career_url)
        
        ats = detection.get('ats', 'unknown')
        
        # STRICT: Only accept known ATS types
        if ats not in cls.SUPPORTED_ATS:
            logger.warning(
                "CollectorFactory: SKIPPING %s (ATS: %s) - Not in supported list %s",
                company_name, ats, cls.SUPPORTED_ATS
            )
            return None
        
        logger.info("CollectorFactory: Creating %s collector for %s", ats, company_name)
        
        # Get collector class
        collector_class = cls._collectors.get(ats)
        
        if not collector_class:
            logger.error("CollectorFactory: No collector registered for %s", ats)
            return None
        
        # Build config
        slug = detection.get('company_slug') or company_name.lower().replace(' ', '-')
        full_config = config or {}
        full_config['ats_type'] = ats
        full_config['company_slug'] = slug
        full_config['api_url'] = detection.get('api_url')
        
        try:
            return collector_class(
                company_name=company_name,
                company_slug=slug,
                config=full_config
            )
        except Exception as e:
            logger.error("CollectorFactory: Failed to create %s collector for %s: %s",
                        ats, company_name, str(e))
            return None
    
    @classmethod
    def create_for_company(cls, company_config: Dict) -> Optional[Any]:
        """
        Create a collector from company configuration.
        
        ⚠️ STRICT: Returns None if ATS not in SUPPORTED_ATS list.
        
        Args:
            company_config: Dict with 'name', 'career_url', 'ats' (optional)
            
        Returns:
            Collector instance OR None
        """
        name = company_config.get('name', 'Unknown')
        url = company_config.get('career_url', '')
        ats = company_config.get('ats')
        
        # If ATS is explicitly configured, validate it
        if ats:
            if ats not in cls.SUPPORTED_ATS:
                logger.warning(
                    "CollectorFactory: SKIPPING %s - ATS '%s' not supported",
                    name, ats
                )
                return None
            
            collector_class = cls._collectors.get(ats)
            if collector_class:
                slug = company_config.get('slug', name.lower().replace(' ', '-'))
                try:
                    return collector_class(
                        company_name=name,
                        company_slug=slug,
                        config=company_config
                    )
                except Exception as e:
                    logger.error("CollectorFactory: Failed to create %s collector: %s", ats, str(e))
                    return None
        
        # If no ATS configured, try auto-detection
        return cls.create(company_name=name, career_url=url, config=company_config)
    
    @classmethod
    def is_supported_ats(cls, ats_type: str) -> bool:
        """Check if ATS type is supported"""
        return ats_type in cls.SUPPORTED_ATS
    
    @classmethod
    def get_supported_ats(cls) -> List[str]:
        """Get list of supported ATS types"""
        return list(cls.SUPPORTED_ATS)


def register_collector(ats_name: str):
    """Decorator to register a collector class"""
    def decorator(cls):
        CollectorFactory.register(ats_name, cls)
        return cls
    return decorator


# Import and register ATS collectors ONLY
from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .smartrecruiters import SmartRecruitersCollector
from .icims_collector import ICimsCollector
from .ats_extractor import WorkdayExtractor, SuccessFactorsExtractor

# Register ATS collectors ONLY
CollectorFactory.register('greenhouse', GreenhouseCollector)
CollectorFactory.register('lever', LeverCollector)
CollectorFactory.register('smartrecruiters', SmartRecruitersCollector)
CollectorFactory.register('icims', ICimsCollector)
CollectorFactory.register('workday', WorkdayExtractor)
CollectorFactory.register('successfactors', SuccessFactorsExtractor)


if __name__ == "__main__":
    print("=" * 60)
    print("COLLECTOR FACTORY - ATS-ONLY MODE")
    print("=" * 60)
    print(f"\nSupported ATS types: {CollectorFactory.get_supported_ats()}")
    print("\n⚠️  NO FALLBACK - Unknown ATS will be SKIPPED")