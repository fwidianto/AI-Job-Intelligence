"""
iCIMS Collector - ATS-specific collector for iCIMS ATS

iCIMS is used by many large enterprises including:
- DHL
- Maersk
- Various Fortune 500 companies

API Pattern:
- /jobs/ - Job listings
- /iCIMS/ - iCIMS endpoints
- /Candidate/ - Candidate portals
"""

import logging
import json
from typing import List, Optional, Dict, Any

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .base import Job, CollectorError

logger = logging.getLogger(__name__)


class ICimsCollector:
    """
    Collector for iCIMS ATS systems.
    
    iCIMS typically exposes job data through:
    - /jobs/ endpoints
    - /iCIMS/ paths
    - JSON APIs
    
    Usage:
        collector = ICimsCollector("DHL", "dhl.com")
        jobs = collector.fetch_jobs()
    """
    
    ATS_NAME = "icims"
    
    # iCIMS API patterns
    API_PATTERNS = [
        "https://{company}.i-execute.com/jobs",
        "https://careers.{company}.com/jobs",
        "https://{company}.apply2jobs.com",
        "https://www.icims.com/companies/{company}",
    ]
    
    def __init__(self, company_name: str, company_slug: str = None, config: Dict = None):
        self.company_name = company_name
        self.company_slug = company_slug or company_name.lower().replace(' ', '-')
        self.config = config or {}
        self.timeout = self.config.get('timeout', 30)
    
    def fetch_jobs(self) -> List[Job]:
        """
        Fetch jobs from iCIMS ATS.
        
        Returns:
            List of Job objects
        """
        if not REQUESTS_AVAILABLE:
            raise CollectorError("requests library not available")
        
        jobs = []
        
        # Try different API patterns
        for pattern in self.API_PATTERNS:
            url = pattern.format(company=self.company_slug)
            
            try:
                result = self._fetch_from_url(url)
                if result:
                    jobs.extend(result)
                    if jobs:
                        break
            except Exception as e:
                logger.debug(f"iCIMS pattern failed for {url}: {e}")
                continue
        
        # If no jobs from patterns, try to detect from company domain
        if not jobs:
            jobs = self._try_company_domain()
        
        logger.info(f"iCIMS: Found {len(jobs)} jobs for {self.company_name}")
        return jobs
    
    def _fetch_from_url(self, url: str) -> List[Job]:
        """Fetch jobs from a specific URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/html',
            }
            
            resp = requests.get(url, timeout=self.timeout, headers=headers)
            
            if resp.status_code != 200:
                return []
            
            content_type = resp.headers.get('content-type', '')
            
            if 'json' in content_type:
                return self._parse_json_response(resp.text, url)
            else:
                return self._parse_html_response(resp.text, url)
                
        except Exception as e:
            logger.debug(f"iCIMS fetch failed for {url}: {e}")
            return []
    
    def _parse_json_response(self, content: str, base_url: str) -> List[Job]:
        """Parse JSON job data"""
        jobs = []
        
        try:
            data = json.loads(content)
            
            # Handle different JSON structures
            if isinstance(data, dict):
                # Look for job arrays
                for key in ['jobs', 'positions', 'results', 'data', 'items']:
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            job = self._parse_job_item(item, base_url)
                            if job:
                                jobs.append(job)
            elif isinstance(data, list):
                for item in data:
                    job = self._parse_job_item(item, base_url)
                    if job:
                        jobs.append(job)
                        
        except json.JSONDecodeError:
            logger.debug("iCIMS: Invalid JSON response")
        
        return jobs
    
    def _parse_job_item(self, item: Dict, base_url: str) -> Optional[Job]:
        """Parse a job item from JSON"""
        try:
            title = item.get('title') or item.get('name') or item.get('jobTitle')
            if not title:
                return None
            
            location = (
                item.get('location') or 
                item.get('city') or 
                item.get('locationCity') or
                item.get('locationName') or
                'Indonesia'
            )
            
            job_id = str(item.get('id') or item.get('jobId') or item.get('requisitionId', ''))
            
            # Get URLs
            url = (
                item.get('url') or 
                item.get('applyUrl') or 
                item.get('link') or
                item.get('absolute_url')
            )
            
            if not url:
                job_id_str = item.get('id', 'unknown')
                url = f"{base_url}/{job_id_str}"
            
            apply_url = (
                item.get('applyUrl') or
                item.get('applicationUrl') or
                url
            )
            
            return Job(
                job_id=f"icims-{job_id[:12]}",
                title=str(title),
                company=self.company_name,
                location=str(location),
                url=str(url),
                apply_url=str(apply_url) if apply_url else str(url),
                source='iCIMS',
                description=str(item.get('description', ''))[:500],
                source_confidence=0.95,  # High confidence for API
                extraction_method='api',
                validated_source=True
            )
            
        except Exception as e:
            logger.debug(f"iCIMS: Failed to parse job item: {e}")
            return None
    
    def _parse_html_response(self, content: str, base_url: str) -> List[Job]:
        """Parse HTML job listings"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            jobs = []
            
            # iCIMS job card selectors
            selectors = [
                '.job-title',
                '.position-title',
                '[class*="job-title"]',
                '[class*="position"]',
                'a[href*="/jobs/"]',
                'a[href*="/position/"]',
            ]
            
            for selector in selectors:
                cards = soup.select(selector)
                for card in cards[:50]:
                    try:
                        title_el = card if card.name in ['h1', 'h2', 'h3', 'h4'] else card.select_one('h1,h2,h3,h4,a')
                        if not title_el:
                            title_el = card
                        
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue
                        
                        link = card.select_one('a[href]') or title_el
                        href = link.get('href') if link else None
                        
                        if href:
                            from urllib.parse import urljoin
                            url = urljoin(base_url, href)
                            
                            location_el = card.select_one('[class*="location"], [class*="city"]')
                            location = location_el.get_text(strip=True) if location_el else 'Indonesia'
                            
                            jobs.append(Job(
                                job_id=f"icims-{hash(title) % 1000000}",
                                title=title,
                                company=self.company_name,
                                location=location,
                                url=url,
                                apply_url=url,
                                source='iCIMS',
                                source_confidence=0.5,  # Lower confidence for HTML
                                extraction_method='html',
                                validated_source=True
                            ))
                    except:
                        continue
                
                if jobs:
                    break
            
            return jobs
        except ImportError:
            return []
        except Exception as e:
            logger.debug(f"iCIMS HTML parsing failed: {e}")
            return []
    
    def _try_company_domain(self) -> List[Job]:
        """Try to find iCIMS jobs from company domain"""
        # Try common iCIMS patterns for company
        patterns = [
            f"https://{self.company_slug}.apply2jobs.com",
            f"https://careers.{self.company_slug}.com/jobs",
            f"https://{self.company_slug}.i-execute.com/jobs",
        ]
        
        for url in patterns:
            jobs = self._fetch_from_url(url)
            if jobs:
                return jobs
        
        return []


def fetch_icims_jobs(company_name: str, company_slug: str = None) -> List[Job]:
    """
    Convenience function to fetch jobs from iCIMS.
    
    Usage:
        jobs = fetch_icims_jobs("DHL", "dhl")
    """
    collector = ICimsCollector(company_name, company_slug)
    return collector.fetch_jobs()