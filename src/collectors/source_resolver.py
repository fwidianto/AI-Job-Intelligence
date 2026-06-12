"""
Job Source Resolver - ATS-Only Job Source Validation

⚠️ STRICT RULE: This module ONLY validates and returns jobs from supported ATS.
NO HTML scraping, NO fallback to generic extraction.

Supported ATS:
- greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
- lever: https://api.lever.co/v0/postings/{slug}?mode=json
- smartrecruiters: https://www.smartrecruiters.com/api/public/postings
- icims: /jobs/ endpoints
- workday: OData/job posting services
- successfactors: OData/SF job services

If a source is NOT one of the above → return empty result (SKIP)
"""

import logging
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .base import Job

logger = logging.getLogger(__name__)


@dataclass 
class ResolverResult:
    """Result of job source resolution"""
    success: bool
    jobs: List[Job] = field(default_factory=list)
    ats_type: str = ""  # greenhouse, lever, workday, etc.
    method_used: str = ""  # 'api', 'html', 'none'
    error: Optional[str] = None


class JobSourceResolver:
    """
    ATS-Only job source resolver.
    
    ⚠️ STRICT: Only returns jobs from supported ATS.
    Unknown/unsupported sources are SKIPPED (no scraping).
    
    Supported ATS:
    - greenhouse, lever, smartrecruiters, icims, workday, successfactors
    
    Usage:
        resolver = JobSourceResolver()
        result = resolver.resolve("https://grab.careers", "Grab")
        
        if result.success:
            for job in result.jobs:
                print(job.title)
        else:
            # SKIP - unsupported source
            pass
    """
    
    SUPPORTED_ATS = {
        'greenhouse', 'lever', 'smartrecruiters', 
        'icims', 'workday', 'successfactors'
    }
    
    # ATS API patterns
    ATS_API_PATTERNS = {
        'greenhouse': 'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs',
        'lever': 'https://api.lever.co/v0/postings/{slug}?mode=json',
        'smartrecruiters': 'https://www.smartrecruiters.com/api/public/postings?company={slug}',
        'icims': 'https://{company}.i-execute.com/jobs',
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def resolve(self, career_url: str, company_name: str = None) -> ResolverResult:
        """
        Resolve job sources from a career URL.
        
        ⚠️ STRICT RULE: Returns empty result if ATS is not in SUPPORTED_ATS.
        
        Pipeline:
        1. Detect ATS type
        2. If not supported → return empty (SKIP)
        3. If supported → fetch via appropriate collector
        
        Args:
            career_url: Career page URL
            company_name: Company name
            
        Returns:
            ResolverResult with jobs OR empty result (skip)
        """
        if not career_url:
            return ResolverResult(success=False, error="No URL provided")
        
        from ..detectors.ats_detector import ATSDetector
        detector = ATSDetector()
        detection = detector.detect(career_url)
        
        ats = detection.get('ats', 'unknown')
        
        # STRICT: Only accept known ATS types
        if ats not in self.SUPPORTED_ATS:
            logger.warning(
                "JobSourceResolver: SKIPPING %s (ATS: %s) - Not supported",
                company_name or 'Unknown', ats
            )
            return ResolverResult(success=False, error=f"Unsupported ATS: {ats}")
        
        slug = detection.get('company_slug') or (company_name or 'unknown').lower().replace(' ', '-')
        
        logger.info(f"JobSourceResolver: Resolving {ats} source for {company_name or slug}")
        
        # Fetch jobs via appropriate collector
        jobs = self._fetch_jobs(ats, company_name or slug, slug)
        
        if jobs:
            return ResolverResult(
                success=True,
                jobs=jobs,
                ats_type=ats,
                method_used='api'
            )
        
        return ResolverResult(success=False, error="No jobs found")
    
    def _fetch_jobs(self, ats: str, company_name: str, slug: str) -> List[Job]:
        """Fetch jobs using the appropriate ATS collector"""
        try:
            if ats == 'greenhouse':
                from .greenhouse import GreenhouseCollector
                collector = GreenhouseCollector(company_name, slug)
                return collector.fetch_jobs()
            
            elif ats == 'lever':
                from .lever import LeverCollector
                collector = LeverCollector(company_name, slug)
                return collector.fetch_jobs()
            
            elif ats == 'smartrecruiters':
                from .smartrecruiters import SmartRecruitersCollector
                collector = SmartRecruitersCollector(company_name, slug)
                return collector.fetch_jobs()
            
            elif ats == 'icims':
                from .icims_collector import ICimsCollector
                collector = ICimsCollector(company_name, slug)
                return collector.fetch_jobs()
            
            elif ats == 'workday':
                from .ats_extractor import WorkdayExtractor
                collector = WorkdayExtractor(company_name, slug)
                return collector.fetch_jobs()
            
            elif ats == 'successfactors':
                from .ats_extractor import SuccessFactorsExtractor
                collector = SuccessFactorsExtractor(company_name, slug)
                return collector.fetch_jobs()
            
        except Exception as e:
            logger.error(f"JobSourceResolver: Failed to fetch {ats} jobs: {e}")
        
        return []


def resolve_job_sources(career_url: str, company_name: str = None) -> ResolverResult:
    """
    Convenience function for job source resolution.
    
    ⚠️ Returns empty result if ATS not supported.
    """
    resolver = JobSourceResolver()
    return resolver.resolve(career_url, company_name)

