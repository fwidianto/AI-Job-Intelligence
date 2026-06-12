"""
Base Collector - Abstract base class for all job collectors

This module defines the interface that all ATS collectors must implement.
Each collector fetches job postings from a specific ATS platform.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Standardized job data model"""
    
    # Unique identifier (format: {ats}_{external_id})
    job_id: str
    
    # Basic job information
    title: str
    company: str
    location: str
    url: str
    source: str  # ATS platform name (e.g., 'Greenhouse', 'Lever')
    
    # Additional details
    description: str = ""  # Full job description (may be empty)
    salary_min: Optional[int] = None  # Monthly in IDR
    salary_max: Optional[int] = None
    employment_type: str = ""  # Full-time, Part-time, Contract
    posted_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    
    # Metadata
    skills: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Original data from API
    
    # ATS/Data Quality fields (v2)
    apply_url: str = ""  # REQUIRED - Must be valid endpoint
    source_confidence: float = 0.5  # 0.0-1.0 (API=0.95, HTML=0.5, Scraped=0.3)
    extraction_method: str = ""  # 'api', 'network_intercept', 'html', 'scraped'
    validated_source: bool = False  # True if source was validated
    
    # Matching results (populated by scoring engine)
    match_score: int = 0  # 0-100
    match_status: str = "NO"  # YES, MAYBE, NO
    match_reasons: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"Job({self.job_id}): {self.title} at {self.company} [{self.match_status}:{self.match_score}] [{self.extraction_method}]"
    
    def is_valid(self) -> bool:
        """Validate job has required fields"""
        return bool(
            self.title and 
            self.company and 
            self.apply_url and  # apply_url is REQUIRED
            self.apply_url.startswith('http')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for storage"""
        return {
            'job_id': self.job_id,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'url': self.url,
            'apply_url': self.apply_url,
            'source': self.source,
            'source_confidence': self.source_confidence,
            'extraction_method': self.extraction_method,
            'validated_source': self.validated_source,
            'description': self.description[:500] if self.description else "",
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'employment_type': self.employment_type,
            'posted_date': self.posted_date.isoformat() if self.posted_date else None,
            'skills': ', '.join(self.skills) if self.skills else '',
            'requirements': ', '.join(self.requirements) if self.requirements else '',
            'match_score': self.match_score,
            'match_status': self.match_status,
            'match_reasons': '; '.join(self.match_reasons),
            'matched_skills': ', '.join(self.matched_skills),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create Job from dictionary"""
        posted = None
        if data.get('posted_date'):
            try:
                posted = datetime.fromisoformat(data['posted_date'])
            except (ValueError, TypeError):
                pass
        
        return cls(
            job_id=data['job_id'],
            title=data['title'],
            company=data['company'],
            location=data['location'],
            url=data['url'],
            source=data['source'],
            description=data.get('description', ''),
            salary_min=data.get('salary_min'),
            salary_max=data.get('salary_max'),
            employment_type=data.get('employment_type', ''),
            posted_date=posted,
            skills=[s.strip() for s in data.get('skills', '').split(',') if s.strip()],
            requirements=[r.strip() for r in data.get('requirements', '').split(',') if r.strip()],
        )


class BaseCollector(ABC):
    """
    Abstract base class for job collectors.
    
    All collectors must implement:
    - fetch_jobs(): Fetch all jobs from the company's ATS
    - normalize_job(): Convert raw job data to standardized Job format
    
    Attributes:
        company_name: Name of the company being monitored
        company_slug: URL-safe company identifier
        base_url: Base URL for the ATS
    """
    
    # Class-level configuration
    ATS_NAME: str = "Base"  # Override in subclass
    API_BASE_URL: str = ""  # Override in subclass
    
    def __init__(self, company_name: str, company_slug: str, config: Optional[Dict] = None):
        """
        Initialize collector.
        
        Args:
            company_name: Full company name (e.g., "Unilever Indonesia")
            company_slug: URL-safe identifier (e.g., "unilever")
            config: Optional company-specific configuration
        """
        self.company_name = company_name
        self.company_slug = company_slug
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.ATS_NAME}")
        
        # Rate limiting
        self.last_request_time: Optional[datetime] = None
        self.min_request_interval: float = 1.0  # Minimum seconds between requests
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests"""
        import time
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = datetime.now()
    
    @abstractmethod
    def fetch_jobs(self) -> List[Job]:
        """
        Fetch all jobs from the company's ATS.
        
        Returns:
            List of Job objects
            
        Raises:
            CollectorError: If fetching fails
        """
        pass
    
    @abstractmethod
    def normalize_job(self, raw_job: Dict[str, Any]) -> Job:
        """
        Convert raw job data from ATS API to standardized Job format.
        
        Args:
            raw_job: Raw job data from ATS API
            
        Returns:
            Standardized Job object
        """
        pass
    
    def get_job_url(self, job_id: str, base_path: str = "") -> str:
        """
        Construct full URL for a job posting.
        
        Args:
            job_id: External job ID
            base_path: Additional path (e.g., "/jobs/12345")
            
        Returns:
            Full URL to job posting
        """
        return urljoin(self.API_BASE_URL, f"{base_path}/{job_id}")
    
    def validate_response(self, response) -> Dict[str, Any]:
        """
        Validate API response and return JSON data.
        
        Args:
            response: requests.Response object
            
        Returns:
            Parsed JSON data
            
        Raises:
            CollectorError: If response is invalid
        """
        if response.status_code == 404:
            raise CollectorError(
                f"Job board not found for {self.company_name}. "
                f"URL: {getattr(self, 'api_url', 'N/A')}. "
                f"Check if the company still uses this ATS platform."
            )
        
        if response.status_code >= 400:
            raise CollectorError(
                f"API error for {self.company_name}: "
                f"HTTP {response.status_code} - {response.text[:200]}"
            )
        
        try:
            return response.json()
        except ValueError as e:
            raise CollectorError(f"Invalid JSON response from {self.company_name}: {e}")


class CollectorError(Exception):
    """Exception raised when collector encounters an error"""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.status_code:
            return f"CollectorError({self.status_code}): {self.message}"
        return f"CollectorError: {self.message}"


class ATSDiscovery:
    """
    ATS Discovery Engine - Identifies which ATS platform a company uses.
    
    Supports:
    - Greenhouse (company.greenhouse.io)
    - Lever (company.lever.co)
    - SmartRecruiters (careers.company.com)
    - Workday (company.workday.com)
    """
    
    # Known ATS patterns
    URL_PATTERNS = {
        'greenhouse': [
            '{slug}.greenhouse.io',
            '{slug}-greenhouse.io',
        ],
        'lever': [
            '{slug}.lever.co',
            '{slug}.workable.com',  # Workable is similar
        ],
        'smartrecruiters': [
            'careers.{slug}.com',
            'www.{slug}-careers.com',
        ],
        'workday': [
            '{slug}.workday.com',
            '{slug}.myworkday.com',
        ],
    }
    
    # Meta tag signatures
    META_SIGNATURES = {
        'greenhouse': ['greenhouse', 'gh-token', 'board-config'],
        'lever': ['lever', 'lever-co'],
        'smartrecruiters': ['smartrecruiters', 'sr-config'],
        'workday': ['workday', 'wd-'],
    }
    
    @classmethod
    def discover(cls, company_name: str, career_url: str, slug: str) -> str:
        """
        Discover ATS platform for a company.
        
        Args:
            company_name: Company name
            career_url: Career page URL
            slug: Company slug
            
        Returns:
            ATS platform name ('greenhouse', 'lever', 'smartrecruiters', 'workday', 'other')
        """
        import requests
        
        # Try URL patterns first
        for ats, patterns in cls.URL_PATTERNS.items():
            for pattern in patterns:
                test_url = pattern.format(slug=slug)
                if not test_url.startswith('http'):
                    test_url = f"https://{test_url}"
                
                try:
                    response = requests.head(test_url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        return ats
                except requests.RequestException:
                    continue
        
        # Try to detect from career page
        try:
            response = requests.get(career_url, timeout=10)
            content = response.text.lower()
            
            for ats, signatures in cls.META_SIGNATURES.items():
                for sig in signatures:
                    if sig in content:
                        return ats
        except requests.RequestException:
            pass
        
        return 'other'
    
    @classmethod
    def get_api_url(cls, company_slug: str, ats: str) -> Optional[str]:
        """
        Get the API endpoint URL for a company's ATS.
        
        Args:
            company_slug: Company slug
            ats: ATS platform
            
        Returns:
            API URL or None if not available
        """
        urls = {
            'greenhouse': f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs",
            'lever': f"https://api.lever.co/v0/postings/{company_slug}?mode=json",
            'smartrecruiters': f"https://www.smartrecruiters.com/api/public/postings?company={company_slug}",
        }
        return urls.get(ats)