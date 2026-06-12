"""
Greenhouse Collector - Fetches jobs from Greenhouse ATS

Greenhouse is used by many tech companies and some MNCs.
API: https://developers.greenhouse.io/job-board.html

Companies known to use Greenhouse:
- Unilever
- Nestlé
- SAP
- GoTo (Gojek/Tokopedia)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
import logging

from .base import BaseCollector, Job, CollectorError

logger = logging.getLogger(__name__)


class GreenhouseCollector(BaseCollector):
    """
    Collector for Greenhouse ATS platform.
    
    Uses the public Job Board API (no authentication required for public jobs).
    """
    
    ATS_NAME = "Greenhouse"
    API_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
    
    def __init__(self, company_name: str, company_slug: str, config: Optional[Dict] = None):
        super().__init__(company_name, company_slug, config)
        self.api_url = f"{self.API_BASE_URL}/{company_slug}/jobs"
        self.logger = logging.getLogger(f"{__name__}.Greenhouse.{company_slug}")
    
    def fetch_jobs(self) -> List[Job]:
        """
        Fetch all jobs from company's Greenhouse job board.
        
        Returns:
            List of Job objects
            
        Raises:
            CollectorError: If API request fails
        """
        self.logger.info(f"Fetching jobs from {self.company_name} (Greenhouse)")
        
        try:
            self._rate_limit()
            response = requests.get(
                self.api_url,
                timeout=30,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': f'Job-Intelligence-Platform/1.0 (contact:{self.config.get("contact_email", "unknown")})'
                }
            )
            
            data = self.validate_response(response)
            jobs = data.get('jobs', [])
            
            self.logger.info(f"Found {len(jobs)} jobs for {self.company_name}")
            
            return [self.normalize_job(raw_job) for raw_job in jobs]
            
        except requests.RequestException as e:
            raise CollectorError(f"Failed to fetch jobs: {e}")
    
    def normalize_job(self, raw_job: Dict[str, Any]) -> Job:
        """
        Convert Greenhouse job data to standardized Job format.
        
        Greenhouse API Response Structure:
        {
            "id": 12345,
            "title": "Business Analyst",
            "location": {"name": "Jakarta, Indonesia"},
            "departments": [{"name": "Finance"}],
            "offices": [{"name": "Jakarta"}],
            "content": "<html>Job description</html>",
            "absolute_url": "https://company.greenhouse.io/jobs/12345",
            "updated_at": "2026-06-10T10:00:00Z",
            "metadata": []
        }
        """
        job_id = f"gh_{raw_job['id']}"
        
        # Parse location
        location = "Not specified"
        if raw_job.get('location') and raw_job['location'].get('name'):
            location = raw_job['location']['name']
        
        # Parse department
        department = ""
        if raw_job.get('departments'):
            department = raw_job['departments'][0].get('name', '')
        
        # Parse posted date
        posted_date = None
        if raw_job.get('updated_at'):
            try:
                posted_date = datetime.fromisoformat(raw_job['updated_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                pass
        
        # Extract description (strip HTML)
        description = self._strip_html(raw_job.get('content', ''))
        
        # Extract skills from description
        skills = self._extract_skills(description)
        
        return Job(
            job_id=job_id,
            title=raw_job['title'],
            company=self.company_name,
            location=location,
            url=raw_job.get('absolute_url', ''),
            source=self.ATS_NAME,
            description=description[:2000],  # Limit length
            employment_type=department,
            posted_date=posted_date,
            skills=skills,
            raw_data=raw_job
        )
    
    def _strip_html(self, html: str) -> str:
        """Remove HTML tags from job description"""
        import re
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Replace br tags with newlines
        html = html.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        html = html.replace('</p>', '\n\n')
        # Remove remaining tags
        html = re.sub(r'<[^>]+>', ' ', html)
        # Decode HTML entities
        html = html.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        # Clean up whitespace
        html = re.sub(r'\s+', ' ', html)
        html = html.strip()
        return html
    
    def _extract_skills(self, description: str) -> List[str]:
        """Extract mentioned skills from job description"""
        # Common skill keywords to look for
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
    collector = GreenhouseCollector(
        company_name="SAP",
        company_slug="sap",
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