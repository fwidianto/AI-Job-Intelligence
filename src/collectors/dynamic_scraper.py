"""
Dynamic Web Scraper - Uses Playwright for JavaScript-rendered pages

This scraper handles modern career sites that require JavaScript rendering:
- Shopee, GoTo, Grab, Astra, etc.

IMPORTANT: This is a fallback layer, used only when static scraping fails.
"""

import logging
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
import hashlib
from urllib.parse import urljoin, urlparse

from .base import Job

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result of a scraping attempt"""
    success: bool
    jobs: List[Job]
    method: str  # 'static', 'dynamic', 'search_fallback'
    error: Optional[str] = None
    jobs_count: int = 0


class DynamicScraper:
    """
    Playwright-based scraper for dynamic JavaScript-rendered career pages.
    """
    
    JOB_CARD_SELECTORS = [
        '[class*="job-card"]',
        '[class*="job-card-item"]',
        '[class*="career-position"]',
        '[class*="position-card"]',
        '[class*="job-listing"]',
        '[class*="vacancy-item"]',
        '[data-keyboard-nav-id]',
        '[data-job-id]',
        '.job-item',
        '.position-item',
        '.vacancy-card',
        'ul.jobs li',
        '.jobs-list .job',
        '[class*="search-result"]',
        '.results .job-result',
    ]
    
    JOB_LINK_SELECTORS = [
        'a[href*="job"]',
        'a[href*="career"]',
        'a[href*="position"]',
        'a[href*="vacancy"]',
        'a.job-link',
        'a.position-link',
    ]
    
    def __init__(self, timeout: int = 30000, headless: bool = True):
        self.timeout = timeout
        self.headless = headless
        self._playwright = None
    
    def _get_playwright(self):
        """Lazy initialization of Playwright"""
        if self._playwright is None:
            try:
                from playwright.sync_api import sync_playwright
                self._playwright = sync_playwright().start()
            except Exception as e:
                logger.error(f"Failed to start Playwright: {e}")
                return None
        return self._playwright
    
    def scrape(self, url: str, company_name: str = None, config: Dict = None) -> ScrapeResult:
        """Scrape jobs from a dynamic JavaScript-rendered page."""
        if config is None:
            config = {}
        
        if company_name is None:
            company_name = urlparse(url).netloc.split('.')[0]
        
        try:
            playwright = self._get_playwright()
            if playwright is None:
                return ScrapeResult(
                    success=False, jobs=[], method='dynamic',
                    error="Playwright not available"
                )
            
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout)
            
            logger.info(f"DynamicScraper: Loading {url}")
            response = page.goto(url, wait_until='networkidle', timeout=self.timeout)
            
            if response is None or response.status >= 400:
                browser.close()
                return ScrapeResult(
                    success=False, jobs=[], method='dynamic',
                    error=f"HTTP {response.status if response else 'No response'}"
                )
            
            self._wait_for_jobs(page)
            self._scroll_page(page)
            jobs = self._extract_jobs(page, company_name, url)
            
            browser.close()
            
            return ScrapeResult(
                success=True, jobs=jobs, method='dynamic', jobs_count=len(jobs)
            )
            
        except Exception as e:
            logger.error(f"DynamicScraper error for {url}: {e}")
            return ScrapeResult(
                success=False, jobs=[], method='dynamic', error=str(e)
            )
    
    def _wait_for_jobs(self, page) -> None:
        """Wait for job listings to load"""
        for selector in ['[class*="job"]', '[class*="position"]', 'ul', 'main']:
            try:
                page.wait_for_selector(selector, timeout=5000)
                break
            except:
                continue
    
    def _scroll_page(self, page) -> None:
        """Scroll page to load lazy content"""
        try:
            for _ in range(3):
                page.evaluate('window.scrollBy(0, 500)')
                time.sleep(0.5)
            page.evaluate('window.scrollTo(0, 0)')
        except Exception as e:
            logger.debug(f"Scroll error: {e}")
    
    def _extract_jobs(self, page, company_name: str, base_url: str) -> List[Job]:
        """Extract job listings from rendered page"""
        jobs = []
        job_elements = self._find_job_cards(page)
        
        for element in job_elements[:50]:
            try:
                job = self._parse_job_element(element, company_name, base_url)
                if job and job.title:
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"Failed to parse job element: {e}")
                continue
        
        return jobs
    
    def _find_job_cards(self, page) -> List:
        """Find job card elements using multiple strategies"""
        elements = []
        for selector in self.JOB_CARD_SELECTORS:
            try:
                found = page.query_selector_all(selector)
                if found:
                    elements.extend(found)
            except:
                continue
        
        seen = set()
        unique = []
        for el in elements:
            try:
                el_id = el.evaluate('el => el.outerHTML.substring(0, 100)')
                if el_id not in seen:
                    seen.add(el_id)
                    unique.append(el)
            except:
                continue
        
        return unique
    
    def _parse_job_element(self, element, company_name: str, base_url: str) -> Optional[Job]:
        """Parse a job card element into a Job object"""
        try:
            title = self._extract_text(element, [
                'h1', 'h2', 'h3', 'h4',
                '[class*="title"]',
                '[class*="name"]',
                '[class*="position"]',
                'a'
            ])
            
            if not title:
                return None
            
            url = self._extract_url(element, base_url)
            location = self._extract_text(element, [
                '[class*="location"]',
                '[class*="city"]',
            ]) or "Indonesia"
            
            description = self._extract_text(element, [
                '[class*="description"]',
                '[class*="requirements"]',
                'p',
            ]) or ""
            
            return Job(
                id=self._generate_id(title, company_name),
                title=title.strip(),
                company=company_name,
                location=location.strip(),
                url=url or base_url,
                source="DynamicScraper",
                description=description.strip()[:500]
            )
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    def _extract_text(self, element, selectors: List[str]) -> Optional[str]:
        """Extract text from element using selectors"""
        for selector in selectors:
            try:
                el = element.query_selector(selector)
                if el:
                    text = el.inner_text().strip()
                    if text:
                        return text
            except:
                continue
        return None
    
    def _extract_url(self, element, base_url: str) -> Optional[str]:
        """Extract URL from element"""
        for selector in self.JOB_LINK_SELECTORS:
            try:
                el = element.query_selector(selector)
                if el:
                    href = el.get_attribute('href')
                    if href:
                        return urljoin(base_url, href)
            except:
                continue
        return None
    
    def _generate_id(self, title: str, company: str) -> str:
        """Generate unique job ID"""
        key = f"{title}-{company}".encode()
        return hashlib.md5(key).hexdigest()[:12]
    
    def close(self):
        """Clean up resources"""
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
            self._playwright = None


def scrape_dynamic(url: str, company_name: str = None) -> ScrapeResult:
    """Convenience function for dynamic scraping."""
    scraper = DynamicScraper()
    try:
        return scraper.scrape(url, company_name)
    finally:
        scraper.close()