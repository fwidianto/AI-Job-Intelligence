"""
Network Intercept Module - Captures API calls via Playwright

This module implements the MANDATORY network intercept mode for discovering
job APIs by capturing XHR/Fetch/GraphQL calls.

Usage:
    interceptor = NetworkInterceptor()
    result = interceptor.capture_job_apis("https://company.careers")
    for api_call in result.apis_found:
        print(f"Found: {api_call.url}")
"""

import logging
import json
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, field
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


@dataclass
class CapturedAPI:
    """An API endpoint captured from network traffic"""
    url: str
    method: str  # GET, POST
    response_type: str  # json, html, xml
    job_count: int = 0
    is_job_endpoint: bool = False
    confidence: float = 0.0
    raw_response: Any = None


@dataclass
class InterceptResult:
    """Result of network intercept operation"""
    success: bool
    career_url: str
    apis_found: List[CapturedAPI] = field(default_factory=list)
    job_apis: List[CapturedAPI] = field(default_factory=list)  # Filtered job APIs
    js_endpoints: List[str] = field(default_factory=list)
    error: Optional[str] = None


class NetworkInterceptor:
    """
    Captures network traffic using Playwright to discover job APIs.
    
    This is the MOST IMPORTANT method for discovering ATS endpoints.
    """
    
    # ATS-specific API URL patterns
    ATS_API_PATTERNS = {
        'greenhouse': [
            '/boards/',
            '/jobs/embed',
            '/v1/boards/',
            'mode=json'
        ],
        'lever': [
            '/v0/postings/',
            'api.lever.co',
            '/postings/'
        ],
        'smartrecruiters': [
            '/api/public/',
            '/search/',
            'rest嗣'
        ],
        'workday': [
            '/wd3/recruiting',
            '/workday',
            '/ RCC'
        ],
        'successfactors': [
            '/sf/vcd/',
            '/odata/v2/',
            'sapsf'
        ],
        'icims': [
            '/jobs/',
            '/iCIMS',
            '/Candidate'
        ]
    }
    
    # Job-related XHR patterns
    JOB_XHR_PATTERNS = [
        'job',
        'position',
        'vacancy',
        'career',
        'listing',
        'requisition',
        'opportunity'
    ]
    
    def __init__(self, timeout: int = 60000, headless: bool = True):
        self.timeout = timeout
        self.headless = headless
        self._playwright = None
        self._captured_requests = []
    
    def capture_job_apis(self, career_url: str) -> InterceptResult:
        """
        Navigate to career URL and capture all network requests.
        
        Args:
            career_url: Career page URL
            
        Returns:
            InterceptResult with captured job APIs
        """
        if not career_url:
            return InterceptResult(success=False, career_url=career_url, error="No URL provided")
        
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return InterceptResult(
                success=False, 
                career_url=career_url, 
                error="Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        
        self._captured_requests = []
        
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            # Capture all requests
            page.on('response', self._handle_response)
            page.on('requestfailed', self._handle_request_failed)
            
            logger.info(f"NetworkInterceptor: Navigating to {career_url}")
            
            # Navigate with extended timeout for SPA loading
            response = page.goto(career_url, wait_until='networkidle', timeout=self.timeout)
            
            if response and response.status >= 400:
                browser.close()
                pw.stop()
                return InterceptResult(
                    success=False,
                    career_url=career_url,
                    error=f"HTTP {response.status}"
                )
            
            # Wait for dynamic content
            time.sleep(2)
            
            # Scroll to trigger lazy loading
            for _ in range(3):
                page.evaluate('window.scrollBy(0, 1000)')
                time.sleep(0.5)
            
            # Look for embedded JSON in page source
            js_endpoints = self._extract_embedded_apis(page.content())
            
            browser.close()
            pw.stop()
            
            # Process captured APIs
            apis = self._process_captured_apis()
            job_apis = self._filter_job_apis(apis)
            
            logger.info(f"NetworkInterceptor: Found {len(job_apis)} job APIs")
            
            return InterceptResult(
                success=True,
                career_url=career_url,
                apis_found=apis,
                job_apis=job_apis,
                js_endpoints=js_endpoints
            )
            
        except Exception as e:
            logger.error(f"NetworkInterceptor error: {e}")
            return InterceptResult(success=False, career_url=career_url, error=str(e))
    
    def _handle_response(self, response) -> None:
        """Handle captured HTTP response"""
        try:
            url = response.url
            content_type = response.headers.get('content-type', '')
            
            # Only capture API-like responses
            if self._is_api_url(url):
                captured = CapturedAPI(
                    url=url,
                    method='GET',  # Assume GET for simplicity
                    response_type='json' if 'json' in content_type else 'html',
                    confidence=self._calculate_confidence(url, content_type)
                )
                self._captured_requests.append(captured)
        except Exception as e:
            logger.debug(f"Response capture error: {e}")
    
    def _handle_request_failed(self, request) -> None:
        """Handle failed requests"""
        pass  # Ignore failed requests for now
    
    def _is_api_url(self, url: str) -> bool:
        """Check if URL looks like an API endpoint"""
        url_lower = url.lower()
        
        # Check for common API patterns
        api_patterns = [
            '/api/', '/v1/', '/v2/', '/v3/',
            '.json', '/jobs', '/postings',
            '/recruiting', '/workday',
            'sapsf', 'greenhouse', 'lever'
        ]
        
        for pattern in api_patterns:
            if pattern in url_lower:
                return True
        
        return False
    
    def _calculate_confidence(self, url: str, content_type: str) -> float:
        """Calculate confidence score for API endpoint"""
        score = 0.5
        
        url_lower = url.lower()
        
        # Higher confidence for known ATS APIs
        for ats, patterns in self.ATS_API_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in url_lower:
                    score += 0.2
        
        # Higher confidence for JSON responses
        if 'json' in content_type:
            score += 0.1
        
        # Higher confidence for job-related keywords
        for keyword in self.JOB_XHR_PATTERNS:
            if keyword in url_lower:
                score += 0.1
        
        return min(score, 1.0)
    
    def _extract_embedded_apis(self, html: str) -> List[str]:
        """Extract API endpoints from embedded JavaScript"""
        endpoints = []
        
        # Look for __INITIAL_STATE__ or similar patterns
        import re
        
        patterns = [
            r'window\.__[\w]+__\s*=\s*(\{[^;]+\})',
            r'"(?:apiUrl|api_url|baseUrl|base_url)"\s*:\s*"([^"]+)"',
            r'(?:api|endpoint|baseUrl)\s*[=:]\s*["\']([^"\']+)["\']',
            r'https://[a-z]+\.lever\.co/api',
            r'https://boards-api\.greenhouse\.io',
            r'https://api\.smartrecruiters\.com',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            endpoints.extend(matches)
        
        return list(set(endpoints))
    
    def _process_captured_apis(self) -> List[CapturedAPI]:
        """Process and deduplicate captured APIs"""
        seen = {}
        apis = []
        
        for api in self._captured_requests:
            if api.url not in seen:
                seen[api.url] = api
                apis.append(api)
        
        return apis
    
    def _filter_job_apis(self, apis: List[CapturedAPI]) -> List[CapturedAPI]:
        """Filter APIs to only job-related endpoints"""
        job_apis = []
        
        for api in apis:
            if self._is_job_api(api):
                api.is_job_endpoint = True
                job_apis.append(api)
        
        # Sort by confidence
        job_apis.sort(key=lambda x: x.confidence, reverse=True)
        
        return job_apis
    
    def _is_job_api(self, api: CapturedAPI) -> bool:
        """Check if API is job-related"""
        url_lower = api.url.lower()
        
        for pattern in self.JOB_XHR_PATTERNS:
            if pattern in url_lower:
                return True
        
        for ats, patterns in self.ATS_API_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in url_lower:
                    return True
        
        return False
    
    def get_job_api_endpoints(self, career_url: str) -> List[str]:
        """
        Convenience method to get just job API endpoints.
        
        Args:
            career_url: Career page URL
            
        Returns:
            List of job API endpoint URLs
        """
        result = self.capture_job_apis(career_url)
        return [api.url for api in result.job_apis]


def intercept_job_apis(career_url: str) -> InterceptResult:
    """
    Convenience function for network interception.
    
    Usage:
        result = intercept_job_apis("https://grab.careers")
        for api in result.job_apis:
            print(f"Job API: {api.url}")
    """
    interceptor = NetworkInterceptor()
    return interceptor.capture_job_apis(career_url)