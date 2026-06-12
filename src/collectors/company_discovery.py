"""
Company URL Discovery - Discovers official job sources

This module resolves company domains to official job sources,
VALIDATING that they contain job data before using them.

DO NOT assume /careers or /career pages are valid job sources.
ALWAYS validate via discovery.
"""

import logging
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSource:
    """A discovered job source"""
    url: str
    source_type: str  # 'api', 'ats', 'career_page', 'job_board'
    ats_type: str = ""  # greenhouse, lever, workday, etc.
    is_valid: bool = False
    confidence: float = 0.0
    job_count_hint: int = 0
    error: Optional[str] = None


@dataclass
class DiscoveryResult:
    """Result of company job source discovery"""
    company: str
    domain: str
    success: bool
    sources: List[DiscoveredSource] = field(default_factory=list)
    primary_source: Optional[DiscoveredSource] = None
    error: Optional[str] = None


class CompanyURLDiscovery:
    """
    Discovers official job sources for a company.
    
    This replaces blind /careers URL assumption with validation.
    
    Usage:
        discovery = CompanyURLDiscovery()
        result = discovery.discover("Shopee")
        if result.success:
            print(f"Primary source: {result.primary_source.url}")
    """
    
    # Known job-related subdomains and paths
    JOB_SUBDOMAINS = [
        'careers', 'jobs', 'career', 'hiring', 'work-with-us',
        'join-us', 'job-openings', 'vacancies', 'opportunities'
    ]
    
    JOB_PATHS = [
        '/careers', '/career', '/jobs', '/hiring', '/work-with-us',
        '/join-us', '/vacancies', '/opportunities',
        '/about/careers', '/about/jobs', '/careers/jobs',
        '/en/careers', '/id/careers'
    ]
    
    # Known ATS domains
    ATS_DOMAINS = {
        'greenhouse': ['boards.greenhouse.io', 'greenhouse.io'],
        'lever': ['boards.lever.co', 'lever.co'],
        'smartrecruiters': ['careers.smartrecruiters.com'],
        'workday': ['workday.com', 'myworkday.com'],
        'successfactors': ['successfactors.com', 'sapsf.com'],
        'icims': ['icims.com'],
    }
    
    # Invalid source patterns
    INVALID_PATTERNS = [
        '/about', '/blog', '/news', '/press', '/investors',
        '/media', '/contact', '/faq', '/help', '/support'
    ]
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
    
    def discover(self, company_name: str, domain: str = None) -> DiscoveryResult:
        """
        Discover job sources for a company.
        
        Args:
            company_name: Company name (e.g., "Shopee")
            domain: Company domain (e.g., "shopee.co.id") - auto-detected if not provided
            
        Returns:
            DiscoveryResult with discovered sources
        """
        if not domain:
            # Auto-detect domain from company name
            domain = self._guess_domain(company_name)
        
        logger.info(f"CompanyURLDiscovery: Discovering sources for {company_name} ({domain})")
        
        sources = []
        
        # Step 1: Check known ATS domains
        ats_sources = self._check_ats_domains(company_name, domain)
        sources.extend(ats_sources)
        
        # Step 2: Check job-related subdomains
        subdomain_sources = self._check_job_subdomains(company_name, domain)
        sources.extend(subdomain_sources)
        
        # Step 3: Check common paths
        path_sources = self._check_common_paths(company_name, domain)
        sources.extend(path_sources)
        
        # Step 4: Validate all sources
        validated_sources = []
        for source in sources:
            if self._validate_source(source):
                source.is_valid = True
                validated_sources.append(source)
        
        # Sort by confidence
        validated_sources.sort(key=lambda x: x.confidence, reverse=True)
        
        primary = validated_sources[0] if validated_sources else None
        
        return DiscoveryResult(
            company=company_name,
            domain=domain,
            success=len(validated_sources) > 0,
            sources=validated_sources,
            primary_source=primary
        )
    
    def _guess_domain(self, company_name: str) -> str:
        """Guess company domain from name"""
        # Common TLDs
        tlds = ['.co.id', '.com', '.co', '.id']
        
        # Normalize company name
        normalized = company_name.lower().replace(' ', '').replace('-', '')
        
        for tld in tlds:
            domain = f"{normalized}{tld}"
            if self._domain_exists(domain):
                return domain
        
        return f"{normalized}.co.id"  # Default to .co.id
    
    def _domain_exists(self, domain: str) -> bool:
        """Check if domain exists"""
        if not REQUESTS_AVAILABLE:
            return False
        
        try:
            url = f"https://www.{domain}"
            resp = requests.head(url, timeout=5, allow_redirects=True)
            return resp.status_code < 500
        except:
            return False
    
    def _check_ats_domains(self, company: str, domain: str) -> List[DiscoveredSource]:
        """Check if company uses known ATS domains"""
        sources = []
        
        for ats_type, ats_domains in self.ATS_DOMAINS.items():
            for ats_domain in ats_domains:
                # Check if company subdomain exists
                subdomain = f"{company.lower().replace(' ', '-')}.{ats_domain}"
                url = f"https://{subdomain}"
                
                source = DiscoveredSource(
                    url=url,
                    source_type='ats',
                    ats_type=ats_type,
                    confidence=0.9 if ats_type in ['greenhouse', 'lever'] else 0.7
                )
                sources.append(source)
        
        return sources
    
    def _check_job_subdomains(self, company: str, domain: str) -> List[DiscoveredSource]:
        """Check job-related subdomains"""
        sources = []
        
        for subdomain in self.JOB_SUBDOMAINS:
            url = f"https://{subdomain}.{domain}"
            
            source = DiscoveredSource(
                url=url,
                source_type='career_page',
                confidence=0.6
            )
            sources.append(source)
        
        return sources
    
    def _check_common_paths(self, company: str, domain: str) -> List[DiscoveredSource]:
        """Check common job-related paths"""
        sources = []
        
        base_url = f"https://www.{domain}"
        
        for path in self.JOB_PATHS:
            url = urljoin(base_url, path)
            
            source = DiscoveredSource(
                url=url,
                source_type='career_page',
                confidence=0.5
            )
            sources.append(source)
        
        return sources
    
    def _validate_source(self, source: DiscoveredSource) -> bool:
        """
        Validate that source actually contains job data.
        
        Returns False for:
        - 404 pages
        - Marketing pages without job data
        - Empty pages
        - Redirects to generic pages
        """
        if not REQUESTS_AVAILABLE:
            return True  # Assume valid if can't check
        
        try:
            resp = requests.get(source.url, timeout=self.timeout, allow_redirects=True)
            
            if resp.status_code != 200:
                source.error = f"HTTP {resp.status_code}"
                return False
            
            content = resp.text.lower()
            
            # Check for invalid patterns
            for pattern in self.INVALID_PATTERNS:
                if pattern in source.url.lower():
                    source.error = "Invalid page type"
                    return False
            
            # Check for job-related content
            job_indicators = [
                'job', 'position', 'vacancy', 'career',
                'apply', 'hiring', 'requisition'
            ]
            
            has_job_content = any(indicator in content for indicator in job_indicators)
            
            if not has_job_content:
                source.error = "No job content found"
                return False
            
            # Check for actual job listings
            job_count = self._estimate_job_count(content)
            source.job_count_hint = job_count
            
            return job_count > 0 or source.source_type == 'ats'
            
        except requests.exceptions.Timeout:
            source.error = "Timeout"
            return False
        except requests.exceptions.RequestException as e:
            source.error = str(e)
            return False
    
    def _estimate_job_count(self, content: str) -> int:
        """Estimate number of jobs on page"""
        # Count job-related patterns
        patterns = [
            r'job[-_]?(?:title|listing|card|item)',
            r'position[-_]?(?:title|listing|card)',
            r'vacancy',
            r'data-job-id',
            r'job-id',
        ]
        
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content, re.IGNORECASE))
        
        return min(count, 100)  # Cap at 100
    
    def find_primary_source(self, company_name: str, domain: str = None) -> Optional[DiscoveredSource]:
        """
        Find the primary job source for a company.
        
        Returns None if no valid source found.
        """
        result = self.discover(company_name, domain)
        return result.primary_source


def discover_company_sources(company_name: str, domain: str = None) -> DiscoveryResult:
    """
    Convenience function for company source discovery.
    
    Usage:
        result = discover_company_sources("Grab")
        if result.success:
            print(f"Use: {result.primary_source.url}")
    """
    discovery = CompanyURLDiscovery()
    return discovery.discover(company_name, domain)