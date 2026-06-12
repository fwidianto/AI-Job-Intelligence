"""
Generic Career Page Scraper - Fallback collector for custom career sites

When ATS detection fails or no API is available, this scraper:
1. Downloads the career page
2. Extracts job links
3. Extracts job titles, locations, and descriptions
4. Returns standardized Job objects

Uses BeautifulSoup for HTML parsing.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("BeautifulSoup4 not installed. Generic scraper unavailable.")

from .base import Job

logger = logging.getLogger(__name__)

class CollectorError(Exception):
    """Exception raised when collector encounters an error"""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class GenericScraper:
    """
    Generic scraper for custom career pages.
    
    Uses pattern matching and heuristics to extract job data from any HTML page.
    Does not extend BaseCollector because it doesn't use a standard ATS API.
    """
    
    ATS_NAME = "GenericScraper"
    
    # Common job listing selectors
    JOB_LINK_PATTERNS = [
        # Direct job links
        r'/jobs?/[\w-]+', 
        r'/careers?/[\w-]+',
        r'/vacancies?/[\w-]+',
        r'/openings?/[\w-]+',
        r'/positions?/[\w-]+',
        # Query parameters
        r'[?&](job|position|vacancy)=',
        r'job_id=',
    ]
    
    # Title extraction patterns
    TITLE_SELECTORS = [
        'h1', 'h2', 'h3',  # Header tags
        '[class*="title"]', '[class*="heading"]',
        '[class*="job-title"]', '[class*="position"]',
        'a.job', 'a.vacancy', 'a.position',
    ]
    
    def __init__(self, company_name: str, career_url: str, config: Optional[Dict] = None):
        """
        Initialize generic scraper.
        
        Args:
            company_name: Full company name
            career_url: URL of the career page
            config: Optional configuration
        """
        self.company_name = company_name
        self.company_slug = company_name.lower().replace(' ', '-')
        self.career_url = career_url
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.Generic.{company_name}")
    
    def fetch_jobs(self) -> List[Job]:
        """
        Fetch jobs from a generic career page.
        
        Returns:
            List of Job objects
            
        Raises:
            CollectorError: If scraping fails
        """
        if not BS4_AVAILABLE:
            raise CollectorError("BeautifulSoup4 is required for generic scraping")
        
        self.logger.info("Scraping jobs from %s", self.career_url)
        
        try:
            import requests
            
            resp = requests.get(
                self.career_url,
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            
            if resp.status_code >= 400:
                raise CollectorError(f"Failed to access career page: HTTP {resp.status_code}")
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extract job links and data
            jobs = self._extract_jobs(soup, resp.url)
            
            self.logger.info("Found %d jobs from generic page", len(jobs))
            return jobs
            
        except Exception as e:
            raise CollectorError(f"Failed to scrape career page: {e}")
    
    def _extract_jobs(self, soup: BeautifulSoup, base_url: str) -> List[Job]:
        """Extract job data from the page"""
        jobs = []
        seen_urls = set()
        
        # Find all links that look like job listings
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Check if this looks like a job link
            if self._is_job_link(href):
                # Resolve full URL
                full_url = urljoin(base_url, href)
                
                # Skip duplicates
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                
                # Extract job data
                job = self._create_job_from_link(link, full_url)
                if job:
                    jobs.append(job)
        
        # Also try to find structured job data (JSON-LD, microdata)
        jobs.extend(self._extract_structured_jobs(soup, base_url))
        
        return jobs
    
    def _is_job_link(self, href: str) -> bool:
        """Check if href looks like a job listing"""
        if not href:
            return False
        
        # Skip navigation and non-job links
        skip_patterns = [
            '/about', '/contact', '/blog', '/news',
            '/faq', '/help', '/privacy', '/terms',
            '/facebook', '/twitter', '/linkedin',
        ]
        
        for pattern in skip_patterns:
            if pattern in href.lower():
                return False
        
        # Check for job patterns
        job_patterns = [
            r'/job[s]?/', r'/career[s]?/', r'/vacanc[y]?/ies?/',
            r'/position[s]?/', r'/opening[s]?/',
            r'/employment', r'/hiring',
        ]
        
        href_lower = href.lower()
        for pattern in job_patterns:
            if re.search(pattern, href_lower):
                return True
        
        return False
    
    def _create_job_from_link(self, link, url: str) -> Optional[Job]:
        """Create a Job object from a link element"""
        try:
            # Get title
            title = link.get_text(strip=True)
            
            # Clean up title
            title = re.sub(r'\s+', ' ', title)
            title = title[:200]  # Limit length
            
            if not title or len(title) < 3:
                return None
            
            # Get location (often near the link)
            location = self._extract_location(link)
            
            # Extract skills from surrounding context
            description = self._extract_description(link)
            
            # Create job ID
            job_id = f"gen_{hash(url)}"
            
            return Job(
                job_id=job_id,
                title=title,
                company=self.company_name,
                location=location,
                url=url,
                source=self.ATS_NAME,
                description=description[:1000],
                skills=self._extract_skills(description)
            )
            
        except Exception as e:
            self.logger.debug("Failed to parse job link: %s", str(e))
            return None
    
    def _extract_location(self, link) -> str:
        """Extract location from near the link"""
        # Look in parent elements for location text
        parent = link.find_parent(['div', 'li', 'article'])
        
        if parent:
            # Look for location indicators
            location_patterns = [
                r'(?:location|place|area|city|region)[\s:]+([A-Za-z\s,]+)',
                r'(?:Jakarta|Surabaya|Bandung|Bali|Remote)',
            ]
            
            text = parent.get_text()
            
            for pattern in location_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        return "Indonesia"
    
    def _extract_description(self, link) -> str:
        """Extract description from near the link"""
        parent = link.find_parent(['div', 'article', 'li'])
        
        if parent:
            text = parent.get_text(strip=True)
            return text[:500]
        
        return ""
    
    def _extract_structured_jobs(self, soup: BeautifulSoup, base_url: str) -> List[Job]:
        """Extract jobs from structured data (JSON-LD, etc)"""
        jobs = []
        
        # Look for JSON-LD structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                
                if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    job = self._parse_json_ld_job(data, base_url)
                    if job:
                        jobs.append(job)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'JobPosting':
                            job = self._parse_json_ld_job(item, base_url)
                            if job:
                                jobs.append(job)
                                
            except (json.JSONDecodeError, KeyError):
                continue
        
        return jobs
    
    def _parse_json_ld_job(self, data: Dict, base_url: str) -> Optional[Job]:
        """Parse a JSON-LD JobPosting object"""
        try:
            title = data.get('title', '')
            url = data.get('url') or data.get('identifier', {}).get('value', '')
            
            if not title:
                return None
            
            # Resolve URL
            if url and not url.startswith('http'):
                url = urljoin(base_url, url)
            
            # Get location
            location_data = data.get('jobLocation', {})
            if isinstance(location_data, dict):
                location = location_data.get('address', {}).get('addressLocality', 'Indonesia')
            else:
                location = 'Indonesia'
            
            # Get description
            description = data.get('description', '')
            
            return Job(
                job_id=f"gen_{hash(url)}" if url else f"gen_{hash(title)}",
                title=title,
                company=self.company_name,
                location=location,
                url=url or '',
                source=self.ATS_NAME,
                description=description[:1000],
                skills=self._extract_skills(description)
            )
            
        except Exception as e:
            self.logger.debug("Failed to parse JSON-LD job: %s", str(e))
            return None
    
    def _extract_skills(self, description: str) -> List[str]:
        """Extract mentioned skills from description"""
        skill_keywords = [
            'SAP', 'Odoo', 'ERP', 'SQL', 'Excel', 'Power BI', 'Tableau',
            'Looker', 'Google Sheets', 'Python', 'Java', 'ETL',
            'Business Intelligence', 'Financial Reporting', 'Budgeting',
            'Forecasting', 'Oracle', 'Workday', 'Salesforce',
            'Business Objects', 'Qlik', 'AWS', 'Azure', 'Jira',
            'Supply Chain', 'Operations', 'Data Analysis', 'Dashboard',
        ]
        
        found = []
        desc_upper = description.upper()
        
        for skill in skill_keywords:
            if skill.upper() in desc_upper:
                found.append(skill)
        
        return found


def scrape_career_page(url: str, company_name: str) -> List[Job]:
    """
    Convenience function to scrape a career page.
    
    Args:
        url: Career page URL
        company_name: Company name
        
    Returns:
        List of Job objects
    """
    scraper = GenericScraper(company_name, url)
    return scraper.fetch_jobs()


if __name__ == "__main__":
    # Test the scraper
    print("=" * 60)
    print("GENERIC SCRAPER TEST")
    print("=" * 60)
    
    # This would require an actual URL to test
    print("\nGenericScraper is ready for use.")
    print("Usage: scrape_career_page('https://company.com/careers', 'Company Name')")