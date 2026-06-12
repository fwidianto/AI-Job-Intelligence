"""
Job Source Resolver - Detects actual job data sources before scraping

This module solves the fundamental problem with modern career pages:
- Career pages are UI shells (SPAs) that load job data via APIs
- Scraping the career page directly returns empty results
- Need to detect and use the underlying job API

Architecture:
1. Detect ATS type from URL
2. Extract known API endpoints for that ATS
3. Try API extraction first (JSON)
4. Fallback to HTML scraping only if API fails
5. Use Playwright only as LAST resort

Supported ATS and their API patterns:
- Greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
- Lever: https://api.lever.co/v0/postings/{slug}?mode=json
- SmartRecruiters: https://www.smartrecruiters.com/api/public/postings?company={slug}
- Workday: No public API (use WorkdayExtractor with HTML/JSON parsing)
- SuccessFactors: No public API (use SuccessFactorsExtractor with HTML/JSON parsing)
"""

import logging
import re
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .base import Job

logger = logging.getLogger(__name__)


@dataclass
class JobSource:
    """
    Represents a discovered job data source.
    
    A source can be:
    - API endpoint (JSON)
    - HTML page with structured data
    - JavaScript-rendered page (requires Playwright)
    """
    source_type: str  # 'api', 'html', 'dynamic'
    url: str
    ats_type: str
    company_name: str
    company_slug: str
    confidence: float = 0.5
    data_format: str = 'json'  # 'json', 'html', 'unknown'
    requires_auth: bool = False
    error: Optional[str] = None


@dataclass 
class ResolverResult:
    """Result of job source resolution"""
    success: bool
    sources: List[JobSource] = field(default_factory=list)
    primary_source: Optional[JobSource] = None
    jobs: List[Job] = field(default_factory=list)
    method_used: str = ""  # 'api', 'html', 'dynamic', 'none'
    error: Optional[str] = None


class JobSourceResolver:
    """
    Resolves actual job data sources before scraping.
    
    This is the KEY layer that prevents scraping UI shells.
    
    Usage:
        resolver = JobSourceResolver()
        result = resolver.resolve("https://shopee.careers", "Shopee")
        
        if result.success:
            for job in result.jobs:
                print(job.title)
    """
    
    # Known API endpoints by company (for Indonesian market)
    KNOWN_API_ENDPOINTS = {
        # Company name -> (slug, API URL pattern)
        'grab': ('grab', 'https://grab.careers/api/v0/postings?mode=json'),
        'shopee': ('shopee', None),  # Uses SuccessFactors
        'goto': ('goto', None),  # Uses Workday
        'gojek': ('gojek', None),
        'tokopedia': ('tokopedia', None),
        'blibli': ('blibli', None),
        'bukalapak': ('bukalapak', None),
        'traveloka': ('traveloka', None),
    }
    
    # ATS API patterns
    ATS_API_PATTERNS = {
        'greenhouse': {
            'pattern': 'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs',
            'format': 'json',
            'requires_auth': False,
        },
        'lever': {
            'pattern': 'https://api.lever.co/v0/postings/{slug}?mode=json',
            'format': 'json',
            'requires_auth': False,
        },
        'smartrecruiters': {
            'pattern': 'https://www.smartrecruiters.com/api/public/postings?company={slug}',
            'format': 'json',
            'requires_auth': False,
        },
        'workday': {
            'pattern': None,  # No public API
            'format': 'html',
            'requires_auth': False,
        },
        'successfactors': {
            'pattern': None,  # No public API
            'format': 'html',
            'requires_auth': False,
        },
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def resolve(self, career_url: str, company_name: str = None) -> ResolverResult:
        """
        Resolve job sources from a career URL.
        
        Priority order:
        1. Known API endpoints (from KNOWN_API_ENDPOINTS)
        2. ATS-specific APIs (Greenhouse, Lever, SmartRecruiters)
        3. HTML scraping (for Workday, SuccessFactors)
        4. Dynamic scraping (Playwright) - LAST RESORT
        
        Args:
            career_url: Career page URL
            company_name: Company name
            
        Returns:
            ResolverResult with jobs and metadata
        """
        if not career_url:
            return ResolverResult(success=False, error="No URL provided")
        
        # Extract company slug
        slug = self._extract_slug(career_url, company_name)
        if not company_name:
            company_name = slug.replace('-', ' ').title()
        
        logger.info(f"JobSourceResolver: Resolving sources for {company_name}")
        
        # Step 1: Check known API endpoints
        source = self._check_known_apis(career_url, company_name, slug)
        if source:
            # Try API extraction
            result = self._try_api_source(source)
            if result.success:
                return result
            # If API fails, try HTML
        
        # Step 2: Detect ATS and get API endpoint
        ats_source = self._detect_ats_api(career_url, company_name, slug)
        if ats_source and ats_source.data_format == 'json':
            result = self._try_api_source(ats_source)
            if result.success:
                return result
        
        # Step 3: Try HTML-based extraction (Workday, SuccessFactors)
        if ats_source:
            result = self._try_html_source(ats_source)
            if result.success:
                return result
        
        # Step 4: Dynamic scraping (LAST RESORT)
        result = self._try_dynamic_source(career_url, company_name)
        return result
    
    def _extract_slug(self, url: str, company_name: str = None) -> str:
        """Extract company slug from URL or name"""
        if company_name:
            return company_name.lower().replace(' ', '-')
        
        parsed = urlparse(url.lower())
        host = parsed.netloc
        
        # Remove common prefixes
        for prefix in ['www.', 'careers.', 'jobs.', 'careers-api.']:
            host = host.replace(prefix, '')
        
        # Get first part
        slug = host.split('.')[0]
        return slug
    
    def _check_known_apis(self, url: str, company_name: str, slug: str) -> Optional[JobSource]:
        """Check if this company has a known API endpoint"""
        # Normalize company name for lookup
        name_lower = company_name.lower().replace(' ', '')
        
        for known_name, (known_slug, api_url) in self.KNOWN_API_ENDPOINTS.items():
            if known_name in name_lower or name_lower in known_name:
                if api_url:
                    return JobSource(
                        source_type='api',
                        url=api_url,
                        ats_type='known',
                        company_name=company_name,
                        company_slug=known_slug,
                        confidence=0.95,
                        data_format='json',
                        requires_auth=False
                    )
        return None
    
    def _detect_ats_api(self, url: str, company_name: str, slug: str) -> Optional[JobSource]:
        """Detect ATS type and get API endpoint if available"""
        parsed = urlparse(url.lower())
        host = parsed.netloc
        path = parsed.path
        
        # Detect ATS from URL
        ats_type = self._detect_ats_from_url(host, path)
        
        if ats_type in self.ATS_API_PATTERNS:
            api_config = self.ATS_API_PATTERNS[ats_type]
            pattern = api_config['pattern']
            
            if pattern:
                # Format the URL with slug
                api_url = pattern.format(slug=slug)
                return JobSource(
                    source_type='api' if pattern else 'html',
                    url=api_url if pattern else url,
                    ats_type=ats_type,
                    company_name=company_name,
                    company_slug=slug,
                    confidence=0.8 if pattern else 0.5,
                    data_format=api_config['format'],
                    requires_auth=api_config['requires_auth']
                )
            else:
                # No public API, need HTML scraping
                return JobSource(
                    source_type='html',
                    url=url,
                    ats_type=ats_type,
                    company_name=company_name,
                    company_slug=slug,
                    confidence=0.7,
                    data_format='html'
                )
        
        # Unknown ATS
        return JobSource(
            source_type='html',
            url=url,
            ats_type='unknown',
            company_name=company_name,
            company_slug=slug,
            confidence=0.3,
            data_format='html'
        )
    
    def _detect_ats_from_url(self, host: str, path: str) -> str:
        """Detect ATS type from URL"""
        url = host + path
        
        # Greenhouse
        if '.greenhouse.io' in url or 'boards.greenhouse' in url:
            slug = host.split('.')[0]
            # Update API pattern with correct slug
            return 'greenhouse'
        
        # Lever
        if '.lever.co' in url or 'lever.co' in url:
            slug = host.split('.')[0]
            return 'lever'
        
        # SmartRecruiters
        if 'smartrecruiters' in url:
            return 'smartrecruiters'
        
        # Workday
        if 'workday.com' in url or 'myworkday' in url:
            return 'workday'
        
        # SuccessFactors
        if 'successfactors' in url or 'sapsf' in url:
            return 'successfactors'
        
        return 'unknown'
    
    def _try_api_source(self, source: JobSource) -> ResolverResult:
        """Try to fetch jobs from an API source"""
        if not REQUESTS_AVAILABLE:
            return ResolverResult(success=False, error="requests library not available")
        
        try:
            logger.info(f"Trying API source: {source.url}")
            
            resp = requests.get(
                source.url,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                }
            )
            
            if resp.status_code != 200:
                return ResolverResult(
                    success=False,
                    error=f"API returned {resp.status_code}",
                    sources=[source]
                )
            
            # Parse JSON
            data = resp.json()
            jobs = self._parse_api_response(data, source)
            
            if jobs:
                logger.info(f"API extraction SUCCESS: {len(jobs)} jobs found")
                return ResolverResult(
                    success=True,
                    sources=[source],
                    primary_source=source,
                    jobs=jobs,
                    method_used='api'
                )
            else:
                return ResolverResult(
                    success=False,
                    error="No jobs in API response",
                    sources=[source]
                )
                
        except requests.exceptions.Timeout:
            return ResolverResult(success=False, error="API timeout", sources=[source])
        except requests.exceptions.RequestException as e:
            return ResolverResult(success=False, error=str(e), sources=[source])
        except json.JSONDecodeError:
            return ResolverResult(success=False, error="Invalid JSON response", sources=[source])
        except Exception as e:
            return ResolverResult(success=False, error=str(e), sources=[source])
    
    def _parse_api_response(self, data: Any, source: JobSource) -> List[Job]:
        """Parse jobs from API response"""
        jobs = []
        
        # Handle different API response formats
        if isinstance(data, dict):
            # Greenhouse format
            if 'jobs' in data:
                for item in data['jobs']:
                    job = self._parse_greenhouse_job(item, source.company_name)
                    if job:
                        jobs.append(job)
            
            # Lever format
            elif isinstance(data, list):
                for item in data:
                    job = self._parse_lever_job(item, source.company_name)
                    if job:
                        jobs.append(job)
            
            # SmartRecruiters format
            elif 'results' in data:
                for item in data['results']:
                    job = self._parse_smartrecruiters_job(item, source.company_name)
                    if job:
                        jobs.append(job)
        
        elif isinstance(data, list):
            for item in data:
                job = self._parse_generic_job(item, source.company_name)
                if job:
                    jobs.append(job)
        
        return jobs
    
    def _parse_greenhouse_job(self, item: dict, company: str) -> Optional[Job]:
        """Parse Greenhouse API job format"""
        try:
            return Job(
                id=str(item.get('id', '')),
                title=item.get('title', ''),
                company=company,
                location=item.get('location', {}).get('name', 'Indonesia') if isinstance(item.get('location'), dict) else item.get('location', 'Indonesia'),
                url=item.get('absolute_url', item.get('url', '')),
                source='Greenhouse API',
                description=item.get('content', '')[:500] if item.get('content') else ''
            )
        except:
            return None
    
    def _parse_lever_job(self, item: dict, company: str) -> Optional[Job]:
        """Parse Lever API job format"""
        try:
            return Job(
                id=str(item.get('id', '')),
                title=item.get('text', ''),
                company=company,
                location=item.get('location', 'Indonesia'),
                url=item.get('absolute_url', item.get('url', '')),
                source='Lever API',
                description=item.get('description', '')[:500] if item.get('description') else ''
            )
        except:
            return None
    
    def _parse_smartrecruiters_job(self, item: dict, company: str) -> Optional[Job]:
        """Parse SmartRecruiters API job format"""
        try:
            return Job(
                id=str(item.get('id', '')),
                title=item.get('title', ''),
                company=company,
                location=item.get('location', {}).get('city', 'Indonesia') if isinstance(item.get('location'), dict) else item.get('location', 'Indonesia'),
                url=item.get('ref', item.get('applyUrl', '')),
                source='SmartRecruiters API',
                description=item.get('description', '')[:500] if item.get('description') else ''
            )
        except:
            return None
    
    def _parse_generic_job(self, item: dict, company: str) -> Optional[Job]:
        """Parse generic job format"""
        try:
            title = item.get('title') or item.get('name') or item.get('jobTitle')
            if not title:
                return None
            
            return Job(
                id=str(item.get('id', hash(title) % 1000000)),
                title=str(title),
                company=company,
                location=item.get('location', 'Indonesia'),
                url=item.get('url') or item.get('applyUrl') or item.get('link', ''),
                source='Job API',
                description=str(item.get('description', ''))[:500]
            )
        except:
            return None
    
    def _try_html_source(self, source: JobSource) -> ResolverResult:
        """Try to extract jobs from HTML page (Workday, SuccessFactors)"""
        try:
            logger.info(f"Trying HTML source: {source.url}")
            
            # Import extractors
            if source.ats_type == 'workday':
                from .ats_extractor import WorkdayExtractor
                extractor = WorkdayExtractor(timeout=self.timeout)
            elif source.ats_type == 'successfactors':
                from .ats_extractor import SuccessFactorsExtractor
                extractor = SuccessFactorsExtractor(timeout=self.timeout)
            else:
                from .generic_scraper import GenericScraper
                extractor = GenericScraper(
                    company_name=source.company_name,
                    career_url=source.url
                )
            
            jobs = extractor.fetch_jobs()
            
            if jobs:
                logger.info(f"HTML extraction SUCCESS: {len(jobs)} jobs found")
                return ResolverResult(
                    success=True,
                    sources=[source],
                    primary_source=source,
                    jobs=jobs,
                    method_used='html'
                )
            else:
                return ResolverResult(
                    success=False,
                    error="No jobs found in HTML",
                    sources=[source]
                )
                
        except Exception as e:
            return ResolverResult(success=False, error=str(e), sources=[source])
    
    def _try_dynamic_source(self, career_url: str, company_name: str) -> ResolverResult:
        """Try Playwright dynamic scraping (LAST RESORT)"""
        try:
            logger.info(f"Trying Dynamic source (LAST RESORT): {career_url}")
            
            from .dynamic_scraper import DynamicScraper
            
            scraper = DynamicScraper(timeout=30000)
            try:
                result = scraper.scrape(career_url, company_name)
                
                if result.success and result.jobs:
                    logger.info(f"Dynamic extraction SUCCESS: {len(result.jobs)} jobs found")
                    return ResolverResult(
                        success=True,
                        jobs=result.jobs,
                        method_used='dynamic'
                    )
                else:
                    return ResolverResult(
                        success=False,
                        error=result.error or "No jobs found via dynamic scraping",
                        method_used='dynamic'
                    )
            finally:
                scraper.close()
                
        except Exception as e:
            return ResolverResult(success=False, error=str(e), method_used='dynamic')


def resolve_job_sources(career_url: str, company_name: str = None) -> ResolverResult:
    """
    Convenience function to resolve job sources.
    
    Usage:
        result = resolve_job_sources("https://shopee.careers", "Shopee")
        for job in result.jobs:
            print(job.title)
    """
    resolver = JobSourceResolver()
    return resolver.resolve(career_url, company_name)