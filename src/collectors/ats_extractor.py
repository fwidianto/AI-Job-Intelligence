"""
ATS Extractor - Handles Workday and SuccessFactors ATS platforms

These enterprise ATS systems often have structured data that can be extracted
through their public APIs or specific page patterns.
"""

import logging
import re
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .base import Job

logger = logging.getLogger(__name__)


@dataclass
class ATSJob:
    """Standardized job format from ATS systems"""
    title: str
    location: str
    url: str
    description: str = ""
    posted_date: str = ""
    job_id: str = ""


class WorkdayExtractor:
    """
    Extractor for Workday ATS career pages.
    
    Workday career pages often have:
    - Public job listing pages with structured HTML
    - JSON data embedded in page
    - Specific URL patterns
    """
    
    # Workday URL patterns
    JOB_LISTING_PATTERNS = [
        r'/careers/jobs/(\d+)',
        r'/jobs/(\d+)',
        r'/job-req/(\d+)',
    ]
    
    # Common selectors for Workday pages
    SELECTORS = {
        'job_card': [
            '.job-title',
            '[class*="job-title"]',
            '[class*="posting-title"]',
            '.wd-job-title',
        ],
        'location': [
            '[class*="location"]',
            '[class*="city"]',
            '[class*="region"]',
        ],
        'department': [
            '[class*="department"]',
            '[class*="team"]',
        ],
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def extract(self, url: str, company_name: str = None) -> List[Job]:
        """
        Extract jobs from Workday career page.
        
        Args:
            url: Career page URL
            company_name: Company name
            
        Returns:
            List of Job objects
        """
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available for Workday extraction")
            return []
        
        if company_name is None:
            company_name = urlparse(url).netloc.split('.')[0]
        
        jobs = []
        
        try:
            # Try to get the page
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            resp = requests.get(url, timeout=self.timeout, headers=headers)
            
            if resp.status_code != 200:
                logger.warning(f"Workday page returned {resp.status_code}: {url}")
                return []
            
            content = resp.text
            
            # Try to extract JSON data first
            json_jobs = self._extract_from_json(content, company_name, url)
            if json_jobs:
                return json_jobs
            
            # Try BeautifulSoup extraction
            soup_jobs = self._extract_from_soup(content, company_name, url)
            if soup_jobs:
                return soup_jobs
            
            # Try to find job links
            link_jobs = self._extract_from_links(content, company_name, url)
            return link_jobs
            
        except requests.exceptions.Timeout:
            logger.warning(f"Workday timeout: {url}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Workday request error: {e}")
            return []
        except Exception as e:
            logger.error(f"Workday extraction error: {e}")
            return []
    
    def _extract_from_json(self, content: str, company_name: str, base_url: str) -> List[Job]:
        """Extract jobs from JSON data embedded in page"""
        jobs = []
        
        # Look for JSON patterns
        json_patterns = [
            r'window\.__(?:INITIAL|REDUX)__\s*=\s*(\{[^;]+\})',
            r'window\.__NEXT_DATA__\s*=\s*(\{[^;]+\})',
            r'"jobs"\s*:\s*\[([^\]]+)\]',
            r'"postings"\s*:\s*\[([^\]]+)\]',
        ]
        
        for pattern in json_patterns:
            try:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    # Try to parse as JSON
                    if json_str.startswith('{'):
                        data = json.loads(json_str)
                        jobs.extend(self._parse_json_data(data, company_name, base_url))
                    elif json_str.startswith('['):
                        # Array of job objects
                        jobs_json = json.loads('[' + json_str + ']')
                        for item in jobs_json:
                            job = self._parse_job_item(item, company_name, base_url)
                            if job:
                                jobs.append(job)
                    
                    if jobs:
                        break
            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"JSON pattern {pattern} failed: {e}")
                continue
        
        return jobs
    
    def _parse_json_data(self, data: dict, company_name: str, base_url: str) -> List[Job]:
        """Recursively parse JSON data for job listings"""
        jobs = []
        
        def search(obj):
            if isinstance(obj, dict):
                # Check if this looks like a job
                if 'title' in obj and ('location' in obj or 'url' in obj):
                    job = self._parse_job_item(obj, company_name, base_url)
                    if job:
                        jobs.append(job)
                # Continue searching
                for v in obj.values():
                    search(v)
            elif isinstance(obj, list):
                for item in obj:
                    search(item)
        
        search(data)
        return jobs
    
    def _parse_job_item(self, item: dict, company_name: str, base_url: str) -> Optional[Job]:
        """Parse a job item from JSON"""
        try:
            title = item.get('title') or item.get('name') or item.get('jobTitle')
            if not title:
                return None
            
            location = (
                item.get('location') or 
                item.get('city') or 
                item.get('primaryLocation') or
                'Indonesia'
            )
            
            url = (
                item.get('url') or 
                item.get('applyUrl') or 
                item.get('absolute_url') or
                item.get('path')
            )
            
            if url and not url.startswith('http'):
                url = urljoin(base_url, url)
            
            job_id = item.get('id') or item.get('jobId') or item.get('requisitionId', '')[:12]
            
            return Job(
                id=str(job_id),
                title=str(title),
                company=company_name,
                location=str(location),
                url=url or base_url,
                source='Workday',
                description=str(item.get('description', ''))[:500]
            )
        except Exception as e:
            logger.debug(f"Failed to parse job item: {e}")
            return None
    
    def _extract_from_soup(self, content: str, company_name: str, base_url: str) -> List[Job]:
        """Extract jobs using BeautifulSoup"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            jobs = []
            
            # Find job cards
            for selector in ['.job', '.job-listing', '[class*="job"]', 'article']:
                cards = soup.select(selector)
                for card in cards[:50]:
                    try:
                        title_el = card.select_one('h1,h2,h3,h4,a')
                        if not title_el:
                            continue
                        
                        title = title_el.get_text(strip=True)
                        if not title:
                            continue
                        
                        # Get link
                        link = card.select_one('a[href]')
                        url = base_url
                        if link and link.get('href'):
                            url = urljoin(base_url, link['href'])
                        
                        # Get location
                        location_el = card.select_one('[class*="location"], [class*="city"]')
                        location = location_el.get_text(strip=True) if location_el else 'Indonesia'
                        
                        if len(title) > 5:  # Filter out navigation links
                            jobs.append(Job(
                                id=f"wd-{hash(title) % 1000000}",
                                title=title,
                                company=company_name,
                                location=location,
                                url=url,
                                source='Workday',
                                description=''
                            ))
                    except:
                        continue
                
                if jobs:
                    break
            
            return jobs
        except ImportError:
            return []
        except Exception as e:
            logger.debug(f"BeautifulSoup extraction failed: {e}")
            return []
    
    def _extract_from_links(self, content: str, company_name: str, base_url: str) -> List[Job]:
        """Extract job URLs from page links"""
        jobs = []
        
        # Find all links that look like job postings
        link_pattern = re.compile(
            r'href=["\']([^"\']*(?:job|career|position|vacancy)[^"\']*)["\']',
            re.IGNORECASE
        )
        
        seen_titles = set()
        for match in link_pattern.finditer(content):
            try:
                href = match.group(1)
                full_url = urljoin(base_url, href)
                
                # Extract title from URL or surrounding text
                title_match = re.search(r'([^/]+)-(?:job|career|position)', full_url, re.I)
                if title_match:
                    title = title_match.group(1).replace('-', ' ').title()
                else:
                    continue
                
                if title not in seen_titles and len(title) > 5:
                    seen_titles.add(title)
                    jobs.append(Job(
                        id=f"wd-{hash(title) % 1000000}",
                        title=title,
                        company=company_name,
                        location='Indonesia',
                        url=full_url,
                        source='Workday',
                        description=''
                    ))
            except:
                continue
        
        return jobs[:50]  # Limit results


class SuccessFactorsExtractor:
    """
    Extractor for SAP SuccessFactors career pages.
    
    SuccessFactors is used by many large enterprises in Indonesia:
    - Shopee, Lazada
    - Various manufacturing companies
    """
    
    # Common SuccessFactors patterns
    SF_API_PATTERNS = [
        r'/sfapi/v1/vacancy/(\w+)',
        r'/careers/(\d+)',
        r'jobRequisition=([^\s&"]+)',
    ]
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def extract(self, url: str, company_name: str = None) -> List[Job]:
        """Extract jobs from SuccessFactors career page"""
        if not REQUESTS_AVAILABLE:
            return []
        
        if company_name is None:
            company_name = urlparse(url).netloc.split('.')[0]
        
        jobs = []
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml',
            }
            
            resp = requests.get(url, timeout=self.timeout, headers=headers)
            
            if resp.status_code != 200:
                return []
            
            content = resp.text
            
            # Try JSON extraction first
            json_jobs = self._extract_from_json(content, company_name, url)
            if json_jobs:
                return json_jobs
            
            # Try BeautifulSoup
            return self._extract_from_soup(content, company_name, url)
            
        except Exception as e:
            logger.error(f"SuccessFactors extraction error: {e}")
            return []
    
    def _extract_from_json(self, content: str, company_name: str, base_url: str) -> List[Job]:
        """Extract from JSON data"""
        jobs = []
        
        # Look for job data in various JSON patterns
        patterns = [
            r'"jobs"\s*:\s*(\[[^\]]+\])',
            r'"vacancies"\s*:\s*(\[[^\]]+\])',
            r'"requisitions"\s*:\s*(\[[^\]]+\])',
        ]
        
        for pattern in patterns:
            try:
                match = re.search(pattern, content)
                if match:
                    json_str = '[' + match.group(1) + ']'
                    data = json.loads(json_str)
                    for item in data:
                        job = self._parse_job_item(item, company_name, base_url)
                        if job:
                            jobs.append(job)
                    if jobs:
                        break
            except:
                continue
        
        return jobs
    
    def _parse_job_item(self, item: dict, company_name: str, base_url: str) -> Optional[Job]:
        """Parse a job item"""
        try:
            title = (
                item.get('title') or 
                item.get('jobTitle') or 
                item.get('name')
            )
            if not title:
                return None
            
            location = item.get('location', 'Indonesia')
            url = item.get('url') or item.get('applyUrl') or base_url
            
            if not url.startswith('http'):
                url = urljoin(base_url, url)
            
            return Job(
                id=str(item.get('id', hash(title) % 1000000)),
                title=str(title),
                company=company_name,
                location=str(location),
                url=url,
                source='SuccessFactors',
                description=str(item.get('description', ''))[:500]
            )
        except:
            return None
    
    def _extract_from_soup(self, content: str, company_name: str, base_url: str) -> List[Job]:
        """Extract using BeautifulSoup"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            jobs = []
            
            # Find job listings
            for selector in [
                '.sf-element-job',
                '.job-listing',
                '[class*="vacancy"]',
                '[class*="position"]',
                'article',
                '.search-result'
            ]:
                cards = soup.select(selector)
                for card in cards[:50]:
                    try:
                        title_el = card.select_one('a,h1,h2,h3')
                        if not title_el:
                            continue
                        
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue
                        
                        link = card.select_one('a[href]')
                        url = base_url
                        if link and link.get('href'):
                            url = urljoin(base_url, link['href'])
                        
                        location = 'Indonesia'
                        loc_el = card.select_one('[class*="location"]')
                        if loc_el:
                            location = loc_el.get_text(strip=True)
                        
                        jobs.append(Job(
                            id=f"sf-{hash(title) % 1000000}",
                            title=title,
                            company=company_name,
                            location=location,
                            url=url,
                            source='SuccessFactors',
                            description=''
                        ))
                    except:
                        continue
                
                if jobs:
                    break
            
            return jobs
        except ImportError:
            return []
        except Exception as e:
            logger.debug(f"SuccessFactors BeautifulSoup failed: {e}")
            return []


# Convenience functions
def extract_workday(url: str, company_name: str = None) -> List[Job]:
    """Extract jobs from Workday career page"""
    extractor = WorkdayExtractor()
    return extractor.extract(url, company_name)


def extract_successfactors(url: str, company_name: str = None) -> List[Job]:
    """Extract jobs from SuccessFactors career page"""
    extractor = SuccessFactorsExtractor()
    return extractor.extract(url, company_name)