"""
ATS Auto-Detector - Automatically identifies ATS platforms from career URLs

Supports detection for:
- Greenhouse
- Lever
- SmartRecruiters
- Workday
- SuccessFactors (SAP)
- Oracle Recruiting
- JobStreet
- Glints
- Kalibrr
- Custom/Generic career pages

Detection methods:
1. URL pattern matching
2. HTML source inspection
3. Meta tag signatures
4. Script references
5. API endpoint patterns
"""

import re
import logging
from typing import Dict, Optional, List
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


# Known ATS URL patterns and signatures
ATS_SIGNATURES = {
    'greenhouse': {
        'url_patterns': [
            r'\.greenhouse\.io',
            r'boards\.greenhouse\.io',
        ],
        'meta_tags': ['greenhouse', 'gh-token', 'board-config'],
        'script_refs': ['greenhouse.io', 'boards.greenhouse.io'],
        'api_endpoints': [
            'boards-api.greenhouse.io',
            '/v1/boards/',
        ]
    },
    'lever': {
        'url_patterns': [
            r'\.lever\.co',
            r'jobs\.lever\.co',
        ],
        'meta_tags': ['lever', 'lever-co', 'lever-recruiting'],
        'script_refs': ['lever.co', 'api.lever.co'],
        'api_endpoints': [
            'api.lever.co',
            '/v0/postings/',
        ]
    },
    'smartrecruiters': {
        'url_patterns': [
            r'smartrecruiters\.com',
            r'careers\..*\.com',
        ],
        'meta_tags': ['smartrecruiters', 'sr-config', 'smart-recruiters'],
        'script_refs': ['smartrecruiters.com'],
        'api_endpoints': [
            'smartrecruiters.com/api',
        ]
    },
    'workday': {
        'url_patterns': [
            r'\.workday\.com',
            r'\.myworkday\.com',
            r'workday\.com',
        ],
        'meta_tags': ['workday', 'wd-runtime', 'workday-paas'],
        'script_refs': ['workday.com', 'wd.runtime'],
        'api_endpoints': [
            'workday.com',
            '/ccx/api/',
        ]
    },
    'successfactors': {
        'url_patterns': [
            r'successfactors\.com',
            r'sap\.successfactors',
            r'jobs\.sap\.com',
        ],
        'meta_tags': ['successfactors', 'sfdc', 'sap'],
        'script_refs': ['successfactors.com', 'salesforce.com'],
        'api_endpoints': [
            'successfactors.com',
            '/sfapi/',
        ]
    },
    'oracle_taleo': {
        'url_patterns': [
            r'taleo\.(oracle|net|com)',
            r'careers\..*\.taleo',
        ],
        'meta_tags': ['taleo', 'oracle-taleo'],
        'script_refs': ['taleo.net', 'oraclecloud'],
        'api_endpoints': [
            'taleo.net',
            '/taleo/',
        ]
    },
    'jobstreet': {
        'url_patterns': [
            r'jobstreet\.com',
            r'jobs\.jobstreet',
        ],
        'meta_tags': ['jobstreet', 'seek'],
        'script_refs': ['jobstreet.com'],
        'api_endpoints': [
            'jobstreet.com',
        ]
    },
    'glints': {
        'url_patterns': [
            r'glints\.com',
            r'glints\.co',
        ],
        'meta_tags': ['glints'],
        'script_refs': ['glints.com'],
        'api_endpoints': [
            'glints.com/api',
        ]
    },
    'kalibrr': {
        'url_patterns': [
            r'kalibrr\.com',
        ],
        'meta_tags': ['kalibrr'],
        'script_refs': ['kalibrr.com'],
        'api_endpoints': [
            'kalibrr.com',
        ]
    },
}


class ATSDetector:
    """
    Auto-detects ATS platform from career page URL.
    
    Usage:
        detector = ATSDetector()
        result = detector.detect('https://careers.unilever.com')
        # result = {'ats': 'greenhouse', 'confidence': 0.95, 'company_slug': 'unilever'}
    """
    
    def __init__(self):
        self.session = None
    
    def detect(self, career_url: str) -> Dict:
        """
        Detect ATS from career page URL.
        
        Args:
            career_url: URL of the company career page
            
        Returns:
            Dict with 'ats', 'confidence', 'company_slug', and 'api_url'
        """
        if not career_url:
            return {'ats': 'unknown', 'confidence': 0.0, 'company_slug': None, 'api_url': None}
        
        career_url = career_url.strip()
        parsed = urlparse(career_url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        
        logger.info("Detecting ATS for: %s", career_url)
        
        # 1. Try URL pattern matching first (fastest)
        result = self._detect_from_url(host, path)
        if result['confidence'] >= 0.8:
            logger.info("Detected via URL: %s (confidence: %.2f)", result['ats'], result['confidence'])
            return result
        
        # 2. Try fetching page and detecting from content
        result = self._detect_from_page(career_url, host, path)
        logger.info("Detected via page: %s (confidence: %.2f)", result['ats'], result['confidence'])
        return result
    
    def _detect_from_url(self, host: str, path: str) -> Dict:
        """Detect ATS from URL patterns"""
        url = host + path
        
        for ats, sigs in ATS_SIGNATURES.items():
            for pattern in sigs.get('url_patterns', []):
                if re.search(pattern, url, re.IGNORECASE):
                    slug = self._extract_slug(host, ats)
                    return {
                        'ats': ats,
                        'confidence': 0.9,
                        'company_slug': slug,
                        'api_url': self._get_api_url(ats, slug)
                    }
        
        return {'ats': 'custom', 'confidence': 0.0, 'company_slug': None, 'api_url': None}
    
    def _detect_from_page(self, career_url: str, host: str, path: str) -> Dict:
        """Detect ATS by fetching and analyzing the page"""
        try:
            import requests
            resp = requests.get(career_url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if resp.status_code != 200:
                return {'ats': 'custom', 'confidence': 0.3, 'company_slug': self._extract_slug(host, 'custom'), 'api_url': None}
            
            content = resp.text.lower()
            
            # Check for meta tags
            for ats, sigs in ATS_SIGNATURES.items():
                for tag in sigs.get('meta_tags', []):
                    if tag in content:
                        slug = self._extract_slug(host, ats)
                        return {
                            'ats': ats,
                            'confidence': 0.7,
                            'company_slug': slug,
                            'api_url': self._get_api_url(ats, slug)
                        }
            
            # Check for script references
            for ats, sigs in ATS_SIGNATURES.items():
                for script in sigs.get('script_refs', []):
                    if script in content:
                        slug = self._extract_slug(host, ats)
                        return {
                            'ats': ats,
                            'confidence': 0.6,
                            'company_slug': slug,
                            'api_url': self._get_api_url(ats, slug)
                        }
            
            return {'ats': 'custom', 'confidence': 0.2, 'company_slug': self._extract_slug(host, 'custom'), 'api_url': None}
            
        except Exception as e:
            logger.warning("Failed to fetch page for detection: %s", str(e))
            return {'ats': 'custom', 'confidence': 0.1, 'company_slug': self._extract_slug(host, 'custom'), 'api_url': None}
    
    def _extract_slug(self, host: str, ats: str) -> Optional[str]:
        """Extract company slug from hostname"""
        # Remove common prefixes and TLD
        slug = host.replace('www.', '').replace('careers.', '').replace('jobs.', '')
        
        # Handle specific ATS patterns
        if ats == 'greenhouse':
            # e.g., unilever.greenhouse.io -> unilever
            slug = slug.split('.')[0]
        elif ats == 'lever':
            # e.g., grab.lever.co -> grab
            slug = slug.split('.')[0]
        elif ats == 'workday':
            # e.g., danone.workday.com -> danone
            slug = slug.split('.')[0]
        elif ats == 'successfactors':
            # e.g., something.successfactors.com -> extract meaningful part
            parts = slug.split('.')
            slug = parts[0] if parts else slug
        
        # Clean up
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        return slug if slug else None
    
    def _get_api_url(self, ats: str, slug: Optional[str]) -> Optional[str]:
        """Get API endpoint URL for the ATS"""
        if not slug:
            return None
        
        api_urls = {
            'greenhouse': f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs',
            'lever': f'https://api.lever.co/v0/postings/{slug}?mode=json',
            'smartrecruiters': f'https://www.smartrecruiters.com/api/public/postings?company={slug}',
        }
        
        return api_urls.get(ats)
    
    def detect_batch(self, career_urls: List[str]) -> List[Dict]:
        """Detect ATS for multiple URLs"""
        results = []
        for url in career_urls:
            results.append(self.detect(url))
        return results


def detect_ats(career_url: str) -> Dict:
    """
    Convenience function for single URL detection.
    
    Args:
        career_url: URL of the career page
        
    Returns:
        Dict with detection results
    """
    detector = ATSDetector()
    return detector.detect(career_url)


if __name__ == "__main__":
    # Test detection
    test_urls = [
        'https://www.unilever.com/careers/',
        'https://grab.com/careers/',
        'https://www.dhl.com/en/careers.html',
        'https://www.sap.com/indonesia/careers',
        'https://www.nestle.com/careers',
        'https://jobs.jobstreet.com/id/en/',
    ]
    
    print("=" * 60)
    print("ATS DETECTION TEST")
    print("=" * 60)
    
    detector = ATSDetector()
    for url in test_urls:
        result = detector.detect(url)
        print(f"\nURL: {url}")
        print(f"  ATS: {result['ats']} (confidence: {result['confidence']:.2f})")
        print(f"  Slug: {result['company_slug']}")
        if result['api_url']:
            print(f"  API: {result['api_url']}")