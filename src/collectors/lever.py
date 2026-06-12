"""
Lever Collector - Fetches jobs from Lever ATS

Lever is popular among tech companies and startups.
API: https://hire.lever.co/v0/postings/{company}

Companies known to use Lever:
- Grab
- Shopee
- Other tech companies
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
import logging

from .base import BaseCollector, Job, CollectorError

logger = logging.getLogger(__name__)


class LeverCollector(BaseCollector):
    """
    Collector for Lever ATS platform.
    
    Uses the public postings API (no authentication required for public jobs).
    """
    
    ATS_NAME = "Lever"
    API_BASE_URL = "https://api.lever.co/v0/postings"
    
    def __init__(self, company_name: str, company_slug: str, config: Optional[Dict] = None):
        super().__init__(company_name, company_slug, config)
        self.api_url = f"{self.API_BASE_URL}/{company_slug}"
        self.logger = logging.getLogger(f"{__name__}.Lever.{company_slug}")
    
    def fetch_jobs(self) -> List[Job]:
        """
        Fetch all jobs from company's Lever job board.
        
        Returns:
            List of Job objects
            
        Raises:
            CollectorError: If API request fails
        """
        self.logger.info(f"Fetching jobs from {self.company_name} (Lever)")
        
        try:
            self._rate_limit()
            # Lever API returns an array of postings
            response = requests.get(
                self.api_url,
                params={'mode': 'json'},  # JSON format
                timeout=30,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': f'Job-Intelligence-Platform/1.0 (contact:{self.config.get("contact_email", "unknown")})'
                }
            )
            
            # Lever returns 200 even if no jobs found, empty array
            if response.status_code == 404:
                raise CollectorError(f"Job board not found for {self.company_name}")
            
            if response.status_code >= 400:
                raise CollectorError(f"API error: {response.status_code} - {response.text}")
            
            # Try to parse JSON
            try:
                raw_data = response.json()
            except ValueError:
                raise CollectorError(f"Invalid JSON response from Lever")
            
            # Handle both array and object response formats
            if isinstance(raw_data, list):
                jobs_data = raw_data
            elif isinstance(raw_data, dict):
                jobs_data = raw_data.get('postings', raw_data.get('results', []))
            else:
                jobs_data = []
            
            self.logger.info(f"Found {len(jobs_data)} jobs for {self.company_name}")
            
            return [self.normalize_job(raw_job) for raw_job in jobs_data]
            
        except requests.RequestException as e:
            raise CollectorError(f"Failed to fetch jobs: {e}")
    
    def normalize_job(self, raw_job: Dict[str, Any]) -> Job:
        """
        Convert Lever job data to standardized Job format.
        
        Lever API Response Structure:
        {
            "id": "abc123",
            "title": "Business Analyst",
            "location": "Jakarta, Indonesia",
            "description": "Job description text",
            "applyUrl": "https://company.lever.co/jobs/abc123",
            "postedAt": "2026-06-10T00:00:00Z",
            "categories": {
                "location": "Jakarta",
                "department": "Operations",
                "team": "Finance",
                "level": "Mid-Level"
            },
            "lists": []  // Additional info
        }
        """
        # Get job ID
        job_id = raw_job.get('id', '')
        if not job_id:
            # Generate ID from title if not provided
            job_id = f"lev_{hash(raw_job.get('title', ''))}"
        
        # Build job URL
        job_url = raw_job.get('absolute_url', raw_job.get('applyUrl', ''))
        if not job_url:
            job_url = f"https://{self.company_slug}.lever.co/jobs/{job_id}"
        
        # Parse location
        location = raw_job.get('location', 'Not specified')
        if not location or location == 'Anywhere':
            location = 'Remote'
        
        # Parse categories
        categories = raw_job.get('categories', {})
        department = categories.get('department', categories.get('team', ''))
        
        # Parse posted date
        posted_date = None
        posted_at = raw_job.get('postedAt', raw_job.get('created', ''))
        if posted_at:
            try:
                posted_date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                pass
        
        # Get description
        description = raw_job.get('description', raw_job.get('text', ''))
        
        # Clean description
        if description:
            import re
            description = re.sub(r'<[^>]+>', ' ', description)
            description = re.sub(r'\s+', ' ', description).strip()
        
        # Extract skills
        skills = self._extract_skills(description)
        
        return Job(
            job_id=f"lev_{job_id}",
            title=raw_job['title'],
            company=self.company_name,
            location=location,
            url=job_url,
            source=self.ATS_NAME,
            description=description[:2000],
            employment_type=department,
            posted_date=posted_date,
            skills=skills,
            raw_data=raw_job
        )
    
    def _extract_skills(self, description: str) -> List[str]:
        """Extract mentioned skills from job description"""
        skill_keywords = [
            'SAP', 'Odoo', 'ERP', 'SQL', 'Excel', 'Power BI', 'Tableau',
            'Looker', 'Google Sheets', 'Python', 'Java', 'ETL', 'Data Analysis',
            'Business Intelligence', 'Financial Reporting', 'Budgeting',
            'Forecasting', 'Oracle', 'Workday', 'Salesforce', 'PowerPoint',
            'Business Objects', 'Qlik', 'Alteryx', 'KNIME', 'AWS', 'Azure',
            'Google Cloud', 'Jira', 'Confluence', 'Tableau', 'MicroStrategy'
        ]
        
        found_skills = []
        desc_upper = description.upper()
        
        for skill in skill_keywords:
            if skill.upper() in desc_upper:
                found_skills.append(skill)
        
        return found_skills


def test_collector():
    """Test the collector with a known company"""
    collector = LeverCollector(
        company_name="Grab",
        company_slug="grab",
        config={"contact_email": "test@example.com"}
    )
    
    try:
        jobs = collector.fetch_jobs()
        print(f"Found {len(jobs)} jobs:")
        for job in jobs[:5]:
            print(f"  - {job.title} ({job.location})")
            print(f"    URL: {job.url}")
    except CollectorError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_collector()