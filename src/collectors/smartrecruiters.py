"""
SmartRecruiters Collector - Fetches jobs from SmartRecruiters ATS

SmartRecruiters is used by various companies including logistics, retail, and enterprise.
API: https://www.smartrecruiters.com/api/public/postings

Companies known to use SmartRecruiters:
- DHL
- Maersk
- Various enterprise companies
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
import logging

from .base import BaseCollector, Job, CollectorError

logger = logging.getLogger(__name__)


class SmartRecruitersCollector(BaseCollector):
    """
    Collector for SmartRecruiters ATS platform.
    
    Uses the public postings API (no authentication required).
    """
    
    ATS_NAME = "SmartRecruiters"
    API_BASE_URL = "https://www.smartrecruiters.com/api/public/postings"
    
    def __init__(self, company_name: str, company_id: str = None, config: Optional[Dict] = None):
        """
        Initialize SmartRecruiters collector.
        
        Args:
            company_name: Full company name
            company_id: SmartRecruiters company ID (or slug)
            config: Optional configuration
        """
        super().__init__(company_name, company_id or company_name.lower().replace(' ', '-'), config)
        # SmartRecruiters uses company ID for API
        self.company_id = company_id or self._slugify(company_name)
        self.api_url = f"{self.API_BASE_URL}"
        self.logger = logging.getLogger(f"{__name__}.SmartRecruiters.{self.company_id}")
    
    def fetch_jobs(self) -> List[Job]:
        """
        Fetch all jobs from company's SmartRecruiters job board.
        
        Returns:
            List of Job objects
            
        Raises:
            CollectorError: If API request fails
        """
        self.logger.info(f"Fetching jobs from {self.company_name} (SmartRecruiters)")
        
        try:
            self._rate_limit()
            # SmartRecruiters API uses company ID as parameter
            response = requests.get(
                self.api_url,
                params={'company': self.company_id},
                timeout=30,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': f'Job-Intelligence-Platform/1.0'
                }
            )
            
            if response.status_code == 404:
                raise CollectorError(f"Job board not found for {self.company_name}")
            
            if response.status_code >= 400:
                raise CollectorError(f"API error: {response.status_code}")
            
            try:
                data = response.json()
            except ValueError:
                raise CollectorError(f"Invalid JSON response")
            
            # SmartRecruiters returns { "content": [...] }
            jobs_data = data.get('content', data.get('results', []))
            
            self.logger.info(f"Found {len(jobs_data)} jobs for {self.company_name}")
            
            return [self.normalize_job(raw_job) for raw_job in jobs_data]
            
        except requests.RequestException as e:
            raise CollectorError(f"Failed to fetch jobs: {e}")
    
    def normalize_job(self, raw_job: Dict[str, Any]) -> Job:
        """
        Convert SmartRecruiters job data to standardized Job format.
        
        SmartRecruiters API Response Structure:
        {
            "id": "xyz789",
            "refNumber": "SR-REF-123",
            "title": "Business Analyst",
            "location": {
                "city": "Jakarta",
                "region": "Jakarta",
                "country": "Indonesia"
            },
            "description": "Job description HTML",
            "jobAd": {
                "sections": {
                    "main": "<html>Description</html>"
                }
            },
            "publishedOn": "2026-06-10T00:00:00Z",
            "company": {
                "name": "Company Name"
            }
        }
        """
        # Get job ID
        job_id = raw_job.get('id', raw_job.get('refNumber', ''))
        if not job_id:
            job_id = f"sr_{hash(raw_job.get('title', ''))}"
        
        # Build job URL
        ref_number = raw_job.get('refNumber', '')
        job_url = f"https://www.smartrecruiters.com/{self.company_id}/{job_id}" if ref_number else ''
        
        # Parse location
        location_data = raw_job.get('location', {})
        if isinstance(location_data, dict):
            city = location_data.get('city', '')
            region = location_data.get('region', '')
            country = location_data.get('country', '')
            location_parts = [p for p in [city, region, country] if p]
            location = ', '.join(location_parts) if location_parts else 'Not specified'
        else:
            location = str(location_data) if location_data else 'Not specified'
        
        # Parse description
        job_ad = raw_job.get('jobAd', {})
        sections = job_ad.get('sections', {})
        description = sections.get('main', '') or raw_job.get('description', '')
        
        if description:
            import re
            description = re.sub(r'<[^>]+>', ' ', description)
            description = re.sub(r'\s+', ' ', description).strip()
        
        # Parse posted date
        posted_date = None
        published = raw_job.get('publishedOn', raw_job.get('created', ''))
        if published:
            try:
                posted_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                pass
        
        # Extract skills
        skills = self._extract_skills(description)
        
        return Job(
            job_id=f"sr_{job_id}",
            title=raw_job['title'],
            company=self.company_name,
            location=location,
            url=job_url,
            source=self.ATS_NAME,
            description=description[:2000],
            employment_type=raw_job.get('type', ''),
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
            'Google Cloud', 'Jira', 'Confluence', 'MicroStrategy'
        ]
        
        found_skills = []
        desc_upper = description.upper()
        
        for skill in skill_keywords:
            if skill.upper() in desc_upper:
                found_skills.append(skill)
        
        return found_skills
    
    def _slugify(self, text: str) -> str:
        """Convert company name to SmartRecruiters company ID format"""
        import re
        # Remove special characters and convert spaces to hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
        slug = slug.lower().replace(' ', '-').strip('-')
        return slug


def test_collector():
    """Test the collector with DHL"""
    collector = SmartRecruitersCollector(
        company_name="DHL",
        company_id="dhl",  # DHL uses lowercase
        config={}
    )
    
    try:
        jobs = collector.fetch_jobs()
        print(f"Found {len(jobs)} jobs:")
        for job in jobs[:5]:
            print(f"  - {job.title} ({job.location})")
    except CollectorError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_collector()