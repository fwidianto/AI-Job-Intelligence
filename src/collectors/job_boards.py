"""
Job Board Collectors - Collect jobs from Indonesian job boards

Supports:
- JobStreet
- Glints  
- Kalibrr

These job boards aggregate jobs from many companies, providing
broader coverage than individual company career pages.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from .base import Job

logger = logging.getLogger(__name__)


class CollectorError(Exception):
    """Exception raised when collector encounters an error"""
    pass


class JobBoardCollector:
    """
    Base class for job board collectors.
    
    Job boards have different structures but similar patterns.
    Does not extend BaseCollector because job boards are not company ATS.
    """
    
    ATS_NAME = "JobBoard"
    
    def __init__(self, company_name: str, board_name: str, search_url: str, config: Optional[Dict] = None):
        self.company_name = company_name
        self.board_name = board_name
        self.search_url = search_url
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{board_name}")
    
    def fetch_jobs(self) -> List[Job]:
        """Fetch jobs from the job board"""
        if not BS4_AVAILABLE:
            raise CollectorError("BeautifulSoup4 is required for job board scraping")
        
        self.logger.info("Fetching jobs from %s", self.board_name)
        
        try:
            import requests
            
            resp = requests.get(
                self.search_url,
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml',
                }
            )
            
            if resp.status_code != 200:
                raise CollectorError(f"Failed to access {self.board_name}: HTTP {resp.status_code}")
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            jobs = self._parse_job_listings(soup, resp.url)
            
            self.logger.info("Found %d jobs from %s", len(jobs), self.board_name)
            return jobs
            
        except Exception as e:
            raise CollectorError(f"Failed to fetch from {self.board_name}: {e}")
    
    def _parse_job_listings(self, soup: BeautifulSoup, base_url: str) -> List[Job]:
        """Parse job listings from the page - override in subclass"""
        raise NotImplementedError("Subclass must implement _parse_job_listings")
    
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


class JobStreetCollector(JobBoardCollector):
    """
    Collector for JobStreet Indonesia.
    
    JobStreet is the largest job board in Indonesia.
    """
    
    ATS_NAME = "JobStreet"
    
    # Search URLs for target roles (multiple fallbacks)
    SEARCH_TEMPLATES = {
        'business_analyst': [
            'https://www.jobstreet.com/id/en/job-search/business-analyst-jobs-in-indonesia/',
            'https://www.jobstreet.co.id/id/en/job-search/business-analyst-jobs/',
        ],
        'erp_analyst': [
            'https://www.jobstreet.com/id/en/job-search/erp-analyst-jobs-in-indonesia/',
        ],
        'data_analyst': [
            'https://www.jobstreet.com/id/en/job-search/data-analyst-jobs-in-indonesia/',
        ],
        'operations_analyst': [
            'https://www.jobstreet.com/id/en/job-search/operations-analyst-jobs-in-indonesia/',
        ],
    }
    
    def __init__(self, company_name: str = "JobStreet", config: Optional[Dict] = None):
        search_url = self.SEARCH_TEMPLATES['business_analyst'][0]
        super().__init__(company_name, "JobStreet", search_url, config)
        self.config = config or {}
        self.timeout = self.config.get('timeout', 15)
    
    def fetch_by_role(self, role: str) -> List[Job]:
        """Fetch jobs for a specific role with fallback URLs"""
        role_slug = role.lower().replace(' ', '-')
        urls = [
            f'https://www.jobstreet.com/id/en/job-search/{role_slug}-jobs-in-indonesia/',
            f'https://www.jobstreet.co.id/id/en/job-search/{role_slug}-jobs/',
        ]
        
        for url in urls:
            try:
                import requests
                from bs4 import BeautifulSoup
                
                resp = requests.get(url, timeout=self.timeout, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
                })
                
                if resp.status_code == 200 and len(resp.text) > 10000:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    jobs = self._parse_job_listings(soup, url)
                    if jobs:
                        self.logger.info("Found %d jobs from %s", len(jobs), url)
                        return jobs
                        
            except Exception as e:
                self.logger.debug("Failed to fetch %s from %s: %s", role, url, str(e))
                continue
        
        self.logger.warning("No jobs found for role: %s", role)
        return []
    
    def _parse_job_listings(self, soup: BeautifulSoup, base_url: str) -> List[Job]:
        """Parse JobStreet job listings with multiple selector strategies"""
        jobs = []
        
        # Strategy 1: Look for job cards with common class patterns
        selectors = [
            {'class': lambda x: x and 'job-card' in str(x).lower()},
            {'class': lambda x: x and 'job-listing' in str(x).lower()},
            {'class': lambda x: x and 'result-item' in str(x).lower()},
            {'data-automation': True},
        ]
        
        for selector in selectors:
            job_cards = soup.find_all(['div', 'article', 'li'], attrs=selector)
            
            for job_card in job_cards:
                try:
                    # Extract job title - try multiple selectors
                    title_elem = (
                        job_card.find('a', attrs={'data-automation': 'jobTitle'}) or
                        job_card.find('a', class_=lambda x: x and 'title' in str(x).lower()) or
                        job_card.find('h2') or
                        job_card.find('h3') or
                        job_card.find('a')
                    )
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 3 or len(title) > 200:
                        continue
                    
                    # Extract URL
                    url = title_elem.get('href', '') or title_elem.get('data-job-url', '')
                    if url and not url.startswith('http'):
                        url = 'https://www.jobstreet.com' + url
                    
                    # Extract company
                    company_elem = (
                        job_card.find('a', attrs={'data-automation': 'jobCompany'}) or
                        job_card.find('span', class_=lambda x: x and 'company' in str(x).lower())
                    )
                    company = company_elem.get_text(strip=True) if company_elem else self.board_name
                    
                    # Extract location
                    location_elem = (
                        job_card.find('span', attrs={'data-automation': 'jobLocation'}) or
                        job_card.find('span', class_=lambda x: x and 'location' in str(x).lower())
                    )
                    location = location_elem.get_text(strip=True) if location_elem else 'Indonesia'
                    
                    # Create job
                    job_id = f"js_{hash(url)}" if url else f"js_{hash(title)}"
                    
                    job = Job(
                        job_id=job_id,
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        source=self.ATS_NAME,
                        description='',
                        skills=[]
                    )
                    
                    jobs.append(job)
                    
                except Exception as e:
                    self.logger.debug("Failed to parse job card: %s", str(e))
                    continue
            
            if jobs:
                break
        
        return jobs


class GlintsCollector(JobBoardCollector):
    """
    Collector for Glints Indonesia.
    
    Glints focuses on tech and startup roles.
    """
    
    ATS_NAME = "Glints"
    
    SEARCH_URLS = {
        'analyst': 'https://glints.com/id/lowongan-kerja/business-analyst/',
        'data': 'https://glints.com/id/lowongan-kerja/data-analyst/',
        'operations': 'https://glints.com/id/lowongan-kerja/operations/',
    }
    
    def __init__(self, company_name: str = "Glints", config: Optional[Dict] = None):
        super().__init__(company_name, "Glints", self.SEARCH_URLS['analyst'], config)
        self.config = config or {}
        self.timeout = self.config.get('timeout', 15)
    
    def _parse_job_listings(self, soup: BeautifulSoup, base_url: str) -> List[Job]:
        """Parse Glints job listings with multiple selector strategies"""
        jobs = []
        
        # Try multiple selectors
        selectors = [
            {'class': lambda x: x and 'job-card' in str(x).lower()},
            {'class': lambda x: x and 'open-position' in str(x).lower()},
            {'class': lambda x: x and 'job-item' in str(x).lower()},
            {'class': lambda x: x and 'card' in str(x).lower()},
        ]
        
        for selector in selectors:
            job_cards = soup.find_all(['div', 'article', 'li'], attrs=selector)
            
            for job_card in job_cards:
                try:
                    title_elem = (
                        job_card.find('a') or
                        job_card.find('h3') or
                        job_card.find('h4') or
                        job_card.find('span')
                    )
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 3 or len(title) > 200:
                        continue
                    
                    url = title_elem.get('href', '')
                    if url and not url.startswith('http'):
                        url = 'https://glints.com' + url
                    
                    # Company
                    company_elem = (
                        job_card.find('span', class_=lambda x: x and 'company' in str(x).lower()) or
                        job_card.find('a', class_=lambda x: x and 'company' in str(x).lower())
                    )
                    company = company_elem.get_text(strip=True) if company_elem else self.board_name
                    
                    # Location
                    location_elem = job_card.find('span', class_=lambda x: x and 'location' in str(x).lower())
                    location = location_elem.get_text(strip=True) if location_elem else 'Indonesia'
                    
                    job = Job(
                        job_id=f"gl_{hash(url)}" if url else f"gl_{hash(title)}",
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        source=self.ATS_NAME,
                        description='',
                        skills=[]
                    )
                    
                    jobs.append(job)
                    
                except Exception as e:
                    self.logger.debug("Failed to parse Glints job: %s", str(e))
                    continue
            
            if jobs:
                break
        
        return jobs


class KalibrrCollector(JobBoardCollector):
    """
    Collector for Kalibrr Indonesia.
    
    Kalibrr focuses on tech and professional roles.
    """
    
    ATS_NAME = "Kalibrr"
    
    SEARCH_URL = 'https://www.kalibrr.com/id/job-board/experienced/business-analyst-in-indonesia/'
    
    def __init__(self, company_name: str = "Kalibrr", config: Optional[Dict] = None):
        super().__init__(company_name, "Kalibrr", self.SEARCH_URL, config)
    
    def _parse_job_listings(self, soup: BeautifulSoup, base_url: str) -> List[Job]:
        """Parse Kalibrr job listings"""
        jobs = []
        
        # Kalibrr uses k-fill class
        for job_card in soup.find_all('a', class_=lambda x: x and 'k-fill' in str(x)):
            try:
                title = job_card.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                
                url = job_card.get('href', '')
                if url and not url.startswith('http'):
                    url = 'https://www.kalibrr.com' + url
                
                # Find parent for company and location
                parent = job_card.find_parent('div')
                
                job = Job(
                    job_id=f"kl_{hash(url)}" if url else f"kl_{hash(title)}",
                    title=title,
                    company='Kalibrr Jobs',
                    location='Indonesia',
                    url=url,
                    source=self.ATS_NAME,
                    description='',
                    skills=[]
                )
                
                jobs.append(job)
                
            except Exception as e:
                self.logger.debug("Failed to parse Kalibrr job: %s", str(e))
                continue
        
        return jobs


def collect_from_all_boards() -> List[Job]:
    """
    Collect jobs from all job boards.
    
    Returns:
        List of all jobs found across JobStreet, Glints, and Kalibrr
    """
    all_jobs = []
    
    # Collect from each board
    collectors = [
        JobStreetCollector(),
        GlintsCollector(),
        KalibrrCollector(),
    ]
    
    for collector in collectors:
        try:
            jobs = collector.fetch_jobs()
            all_jobs.extend(jobs)
            logger.info("Collected %d jobs from %s", len(jobs), collector.board_name)
        except Exception as e:
            logger.error("Failed to collect from %s: %s", collector.board_name, str(e))
    
    return all_jobs


if __name__ == "__main__":
    print("=" * 60)
    print("JOB BOARD COLLECTORS")
    print("=" * 60)
    print("\nAvailable collectors:")
    print("  - JobStreetCollector")
    print("  - GlintsCollector")
    print("  - KalibrrCollector")
    print("\nUsage: collect_from_all_boards()")