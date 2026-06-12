"""
Search-Based Job Discovery Engine

This module provides search-driven job discovery as the PRIMARY method
for finding jobs when APIs are not available.

Search Strategy:
1. Search for company-specific job listings
2. Search for job board aggregations
3. Extract job URLs from search results
4. Route to appropriate collector

Search Queries:
- "site:careers.{company}.co.id analyst jakarta"
- "{company} career data analyst jakarta"
- "site:jobstreet.com {role} jakarta"
- "site:linkedin.com/jobs {company} {role}"

This replaces fragile scraping of homepage career pages.
"""

import logging
import re
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .base import Job

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A job found through search"""
    title: str
    company: str
    url: str
    location: str = "Indonesia"
    source: str = "search"
    snippet: str = ""
    search_engine: str = "duckduckgo"
    relevance_score: float = 0.5


@dataclass
class SearchDiscoveryResult:
    """Result of search-based job discovery"""
    success: bool
    jobs: List[Job] = field(default_factory=list)
    queries_used: List[str] = field(default_factory=list)
    sources_found: List[str] = field(default_factory=list)
    error: Optional[str] = None


class SearchJobDiscovery:
    """
    Search-based job discovery engine.
    
    Uses DuckDuckGo and Google to find job postings from search results.
    This is more reliable than scraping homepage career pages.
    
    Usage:
        discovery = SearchJobDiscovery()
        result = discovery.search("Shopee data analyst jakarta")
        for job in result.jobs:
            print(job.title, job.url)
    """
    
    # Indonesian job boards to search
    JOB_BOARD_DOMAINS = [
        'jobstreet.com',
        'jobstreet.co.id',
        'glints.com',
        'glints.co.id',
        'kalibrr.com',
        'linkedin.com',
        'indeed.com',
        'jobs.id',
    ]
    
    # Career page domains for Indonesian companies
    COMPANY_CAREER_DOMAINS = [
        'careers.shopee.co.id',
        'careers.grab.com',
        'careers.goto.com',
        'careers.astradb.com',
        'careers.unilever.com',
        'careers.nestle.com',
        'careers.danone.com',
    ]
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = None
    
    def search(self, query: str, max_results: int = 20) -> SearchDiscoveryResult:
        """
        Search for jobs using a query string.
        
        Args:
            query: Search query (e.g., "Shopee data analyst jakarta")
            max_results: Maximum number of results to return
            
        Returns:
            SearchDiscoveryResult with found jobs
        """
        if not REQUESTS_AVAILABLE:
            return SearchDiscoveryResult(
                success=False,
                error="requests library not available"
            )
        
        queries_used = [query]
        all_jobs = []
        sources_found = []
        
        try:
            # Try DuckDuckGo first (no API key required)
            ddg_results = self._search_duckduckgo(query, max_results)
            if ddg_results:
                all_jobs.extend(ddg_results)
                sources_found.append("duckduckgo")
            
            # Try Google search (if available via scraping)
            google_results = self._search_google(query, max_results)
            if google_results:
                all_jobs.extend(google_results)
                sources_found.append("google")
            
            # Deduplicate by URL
            seen_urls = set()
            unique_jobs = []
            for job in all_jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    unique_jobs.append(job)
            
            return SearchDiscoveryResult(
                success=len(unique_jobs) > 0,
                jobs=unique_jobs[:max_results],
                queries_used=queries_used,
                sources_found=sources_found
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return SearchDiscoveryResult(
                success=False,
                error=str(e),
                queries_used=queries_used
            )
    
    def search_by_company(self, company: str, roles: List[str] = None, 
                         locations: List[str] = None) -> SearchDiscoveryResult:
        """
        Search for jobs at a specific company.
        
        Args:
            company: Company name
            roles: List of target roles
            locations: List of target locations
            
        Returns:
            SearchDiscoveryResult with found jobs
        """
        if roles is None:
            roles = ['analyst', 'business analyst', 'data analyst', 'erp']
        if locations is None:
            locations = ['jakarta', 'indonesia', 'remote']
        
        all_jobs = []
        queries_used = []
        sources_found = []
        
        # Generate search queries
        for role in roles[:3]:  # Limit to 3 roles
            for location in locations[:2]:  # Limit to 2 locations
                query = f"{company} {role} {location}"
                queries_used.append(query)
                
                result = self.search(query, max_results=10)
                if result.jobs:
                    all_jobs.extend(result.jobs)
                    sources_found.extend(result.sources_found)
        
        # Deduplicate
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                job.company = company  # Normalize company name
                unique_jobs.append(job)
        
        return SearchDiscoveryResult(
            success=len(unique_jobs) > 0,
            jobs=unique_jobs,
            queries_used=queries_used,
            sources_found=list(set(sources_found))
        )
    
    def search_by_role(self, role: str, locations: List[str] = None,
                       job_boards: bool = True) -> SearchDiscoveryResult:
        """
        Search for jobs by role across job boards.
        
        Args:
            role: Target role (e.g., "ERP Analyst")
            locations: Target locations
            job_boards: Search job boards specifically
            
        Returns:
            SearchDiscoveryResult with found jobs
        """
        if locations is None:
            locations = ['jakarta', 'indonesia', 'bekasi']
        
        all_jobs = []
        queries_used = []
        sources_found = []
        
        # Generate queries
        search_domains = []
        if job_boards:
            search_domains.extend(self.JOB_BOARD_DOMAINS)
        
        for location in locations[:3]:
            for domain in search_domains[:4]:  # Limit domains
                query = f"site:{domain} {role} {location}"
                queries_used.append(query)
                
                result = self.search(query, max_results=15)
                if result.jobs:
                    all_jobs.extend(result.jobs)
                    sources_found.extend(result.sources_found)
        
        # Also do a general search
        general_query = f"{role} jakarta indonesia 2024"
        queries_used.append(general_query)
        result = self.search(general_query, max_results=20)
        if result.jobs:
            all_jobs.extend(result.jobs)
            sources_found.extend(result.sources_found)
        
        # Deduplicate
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)
        
        return SearchDiscoveryResult(
            success=len(unique_jobs) > 0,
            jobs=unique_jobs,
            queries_used=queries_used,
            sources_found=list(set(sources_found))
        )
    
    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """
        Search using DuckDuckGo HTML (no API required).
        
        Note: This is for educational purposes. Production should use
        official search APIs (Google Custom Search, Bing, etc.)
        """
        results = []
        
        try:
            # DuckDuckGo HTML search
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            resp = requests.get(url, timeout=self.timeout, headers=headers)
            
            if resp.status_code != 200:
                return results
            
            # Parse results
            html = resp.text
            
            # Find result links and titles
            link_pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
            for match in re.finditer(link_pattern, html):
                url = match.group(1)
                title = match.group(2).strip()
                
                # Skip non-job URLs
                if not self._is_job_url(url):
                    continue
                
                # Extract snippet
                snippet = self._extract_snippet(html, url)
                
                # Extract company from URL
                company = self._extract_company_from_url(url)
                
                results.append(SearchResult(
                    title=title,
                    company=company,
                    url=url,
                    location=self._extract_location(title + ' ' + snippet),
                    source='duckduckgo',
                    snippet=snippet[:200],
                    relevance_score=0.7
                ))
                
                if len(results) >= max_results:
                    break
            
            # Also try JSON API
            if not results:
                json_url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_redirect=1"
                json_resp = requests.get(json_url, timeout=self.timeout, headers=headers)
                
                if json_resp.status_code == 200:
                    data = json_resp.json()
                    if 'RelatedTopics' in data:
                        for topic in data['RelatedTopics'][:max_results]:
                            if 'URL' in topic and 'Text' in topic:
                                url = topic['URL']
                                if self._is_job_url(url):
                                    results.append(SearchResult(
                                        title=topic['Text'][:100],
                                        company=self._extract_company_from_url(url),
                                        url=url,
                                        source='duckduckgo',
                                        relevance_score=0.5
                                    ))
                    
        except Exception as e:
            logger.debug(f"DuckDuckGo search failed: {e}")
        
        return results
    
    def _search_google(self, query: str, max_results: int) -> List[SearchResult]:
        """
        Search using Google (requires Google API key for production).
        
        For production, use:
        - Google Custom Search API
        - SerpAPI
        - RapidAPI Google Search
        """
        # Placeholder - Google scraping is not reliable
        # Use official APIs in production
        return []
    
    def _is_job_url(self, url: str) -> bool:
        """Check if URL is likely a job posting"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Job-related keywords
        job_keywords = [
            'job', 'jobs', 'career', 'careers', 'position', 'vacancy',
            'opportunity', 'listing', 'hire', 'hiring'
        ]
        
        # Job board domains
        job_domains = [
            'jobstreet', 'glints', 'kalibrr', 'linkedin',
            'indeed', 'jobs.id', 'careerjet'
        ]
        
        # Check domain
        for domain in job_domains:
            if domain in url_lower:
                return True
        
        # Check path
        for keyword in job_keywords:
            if keyword in url_lower:
                return True
        
        # Skip non-job pages
        skip_patterns = ['about', 'blog', 'news', 'press', 'investor']
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        return True
    
    def _extract_snippet(self, html: str, url: str) -> str:
        """Extract search snippet for a URL"""
        # Find snippet near the URL
        pattern = f'<a class="result__a" href="{re.escape(url)}"[^>]*>[^<]+</a>.*?<a class="result__snippet"[^>]*>([^<]+)</a>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Try alternative pattern
        pattern = f'class="result__snippet"[^>]*>[^<]*'
        return ""
    
    def _extract_company_from_url(self, url: str) -> str:
        """Extract company name from job URL"""
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower()
            
            # Remove www
            host = host.replace('www.', '')
            
            # Extract company name
            for domain in ['jobstreet', 'glints', 'kalibrr', 'linkedin', 'indeed']:
                if domain in host:
                    return domain.title()
            
            # For company career pages
            parts = host.split('.')
            if len(parts) > 0:
                return parts[0].replace('-', ' ').title()
            
            return 'Unknown'
        except:
            return 'Unknown'
    
    def _extract_location(self, text: str) -> str:
        """Extract location from text"""
        locations = [
            'jakarta', 'bandung', 'surabaya', 'bali', 'bekasi',
            'karawang', 'tangerang', 'bogor', 'depok',
            'indonesia', 'remote', 'work from home'
        ]
        
        text_lower = text.lower()
        for loc in locations:
            if loc in text_lower:
                return loc.title()
        
        return 'Indonesia'


def search_jobs(query: str, max_results: int = 20) -> SearchDiscoveryResult:
    """
    Convenience function for job search.
    
    Usage:
        result = search_jobs("Shopee data analyst jakarta")
        for job in result.jobs:
            print(job.title, job.url)
    """
    discovery = SearchJobDiscovery()
    return discovery.search(query, max_results)


def search_company_jobs(company: str, roles: List[str] = None) -> SearchDiscoveryResult:
    """
    Search for jobs at a specific company.
    
    Usage:
        result = search_company_jobs("Shopee", ["data analyst", "erp analyst"])
    """
    discovery = SearchJobDiscovery()
    return discovery.search_by_company(company, roles)