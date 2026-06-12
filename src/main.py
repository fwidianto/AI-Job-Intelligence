"""
Job Intelligence Platform - Main Entry Point

This script orchestrates the entire job intelligence workflow:
1. Load configuration
2. Collect jobs from ATS platforms
3. Score jobs against user profile
4. Store results in Google Sheets
5. Send email notifications
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.collectors import GreenhouseCollector, LeverCollector, SmartRecruitersCollector
from src.collectors.base import Job, CollectorError
from src.scorer import JobScorer, MatchResult, MatchStatus
from src.sheets import SheetConfig, create_sheets_manager, MockSheetsManager
from src.notifier import create_notifier, MockEmailNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/job_intelligence.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


class JobIntelligencePlatform:
    """
    Main platform class that orchestrates the job intelligence workflow.
    """
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize the platform.
        
        Args:
            config_dir: Path to configuration directory
        """
        self.config_dir = config_dir
        self.user_profile = None
        self.companies = []
        self.scorer = None
        self.sheets_manager = None
        self.notifier = None
        
        logger.info("Initializing Job Intelligence Platform...")
        
        # Load configurations
        self._load_configurations()
        
        # Initialize components
        self._initialize_components()
    
    def _load_configurations(self):
        """Load user profile and companies configuration"""
        
        # Load user profile
        profile_path = os.path.join(self.config_dir, "user_profile.yaml")
        if os.path.exists(profile_path):
            with open(profile_path, 'r', encoding='utf-8') as f:
                self.user_profile = yaml.safe_load(f)
                logger.info(f"Loaded user profile: {len(self.user_profile.get('target_roles', []))} target roles")
        else:
            logger.error(f"User profile not found: {profile_path}")
            raise FileNotFoundError(f"Configuration file not found: {profile_path}")
        
        # Load companies
        companies_path = os.path.join(self.config_dir, "companies.yaml")
        if os.path.exists(companies_path):
            with open(companies_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.companies = config.get('companies', [])
                logger.info(f"Loaded {len(self.companies)} target companies")
        else:
            logger.error(f"Companies config not found: {companies_path}")
            raise FileNotFoundError(f"Configuration file not found: {companies_path}")
    
    def _initialize_components(self):
        """Initialize scorer, sheets manager, and notifier"""
        
        # Initialize scorer
        self.scorer = JobScorer(self.user_profile)
        logger.info("Scoring engine initialized")
        
        # Initialize sheets manager
        sheets_config = SheetConfig(
            spreadsheet_id=os.environ.get('GOOGLE_SHEETS_ID', ''),
            credentials_file=os.environ.get('GOOGLE_CREDENTIALS', 'credentials/credentials.json')
        )
        
        if sheets_config.spreadsheet_id:
            self.sheets_manager = create_sheets_manager(sheets_config)
            logger.info(f"Google Sheets connected: {sheets_config.spreadsheet_id}")
        else:
            self.sheets_manager = MockSheetsManager()
            logger.info("Using mock Sheets manager (set GOOGLE_SHEETS_ID to enable)")
        
        # Initialize notifier
        email_config = self.user_profile.get('email', {})
        if email_config.get('enabled', False) and email_config.get('smtp_user'):
            self.notifier = create_notifier(email_config)
            logger.info(f"Email notifications enabled: {email_config.get('smtp_user')}")
        else:
            self.notifier = MockEmailNotifier({'enabled': True})
            logger.info("Using mock email notifier (enable in user_profile.yaml to send real emails)")
    
    def run(self, force_email: bool = False):
        """
        Run the complete job intelligence workflow.
        
        Args:
            force_email: Force sending email even if no new matches
        """
        logger.info("=" * 60)
        logger.info("Starting Job Intelligence Platform")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        all_jobs = []
        errors = []
        
        # Process each company
        for company in self.companies:
            ats = company.get('ats', 'other')
            
            # Skip companies without working collectors
            if ats not in ['greenhouse', 'lever', 'smartrecruiters']:
                logger.info(f"⏭️  Skipping {company['name']} ({ats} - no collector)")
                continue
            
            logger.info(f"\n📊 Processing: {company['name']} ({ats})")
            
            try:
                # Get collector
                collector = self._get_collector(company)
                if not collector:
                    continue
                
                # Fetch jobs
                jobs = collector.fetch_jobs()
                logger.info(f"   Found {len(jobs)} jobs")
                
                # Score and process each job
                for job in jobs:
                    # Score job
                    match_result = self.scorer.score_job(job)
                    job.match_score = match_result.score
                    
                    # Prepare job data for storage
                    job_data = {
                        'job_id': job.job_id,
                        'date_found': datetime.now().strftime('%Y-%m-%d'),
                        'company': job.company,
                        'title': job.title,
                        'location': job.location,
                        'url': job.url,
                        'source': job.source,
                        'match_status': match_result.status.value,
                        'match_score': match_result.score,
                        'match_reasons': ' | '.join(match_result.reasons),
                        'matched_skills': ', '.join(match_result.matched_skills),
                    }
                    
                    # Add to collection
                    all_jobs.append({
                        'job': job,
                        'result': match_result,
                        'data': job_data
                    })
                    
                    # Log match
                    if match_result.status == MatchStatus.YES:
                        logger.info(f"   ✅ YES: {job.title} ({match_result.score}/100)")
                    elif match_result.status == MatchStatus.MAYBE:
                        logger.info(f"   ⚠️ MAYBE: {job.title} ({match_result.score}/100)")
                
            except CollectorError as e:
                logger.error(f"   ❌ Error: {e}")
                errors.append(f"{company['name']}: {e}")
            except Exception as e:
                logger.error(f"   ❌ Unexpected error: {e}")
                errors.append(f"{company['name']}: {e}")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        
        yes_matches = [j for j in all_jobs if j['result'].status == MatchStatus.YES]
        maybe_matches = [j for j in all_jobs if j['result'].status == MatchStatus.MAYBE]
        
        logger.info(f"Total jobs collected: {len(all_jobs)}")
        logger.info(f"YES matches: {len(yes_matches)}")
        logger.info(f"MAYBE matches: {len(maybe_matches)}")
        
        if errors:
            logger.warning(f"Errors encountered: {len(errors)}")
            for error in errors:
                logger.warning(f"  - {error}")
        
        # Store in Google Sheets
        new_jobs = self._store_jobs(all_jobs)
        logger.info(f"\nNew jobs added to sheet: {new_jobs}")
        
        # Send email notification
        high_matches = [j for j in all_jobs if j['result'].score >= 80 and j['result'].status == MatchStatus.YES]
        
        if high_matches or force_email:
            job_dicts = [j['data'] for j in high_matches]
            if job_dicts:
                self.notifier.send_job_alert(job_dicts)
                logger.info(f"Sent email with {len(high_matches)} high-priority matches")
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n⏱️  Completed in {duration:.1f} seconds")
        logger.info("=" * 60)
        
        return {
            'total_jobs': len(all_jobs),
            'yes_matches': len(yes_matches),
            'maybe_matches': len(maybe_matches),
            'new_jobs': new_jobs,
            'errors': len(errors),
            'duration_seconds': duration
        }
    
    def _get_collector(self, company: Dict[str, Any]):
        """Get the appropriate collector for a company"""
        
        ats = company.get('ats', '')
        name = company.get('name', '')
        slug = company.get('slug', name.lower().replace(' ', '-'))
        
        config = {
            'contact_email': self.user_profile.get('email', {}).get('from_addr', 'unknown@example.com')
        }
        
        if ats == 'greenhouse':
            return GreenhouseCollector(name, slug, config)
        elif ats == 'lever':
            return LeverCollector(name, slug, config)
        elif ats == 'smartrecruiters':
            return SmartRecruitersCollector(name, slug, config)
        else:
            return None
    
    def _store_jobs(self, jobs: List[Dict[str, Any]]) -> int:
        """
        Store jobs in Google Sheets.
        
        Returns:
            Number of new jobs added
        """
        new_count = 0
        
        for job_info in jobs:
            job_data = job_info['data']
            job_id = job_data['job_id']
            
            # Check if job already exists
            if self.sheets_manager.job_exists(job_id):
                continue
            
            # Add new job
            if self.sheets_manager.add_job(job_data):
                new_count += 1
        
        return new_count
    
    def add_job_manually(self, job_data: Dict[str, Any]):
        """Manually add a job to the tracking system"""
        
        # Create Job object
        job = Job(
            job_id=job_data.get('job_id', f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"),
            title=job_data.get('title', ''),
            company=job_data.get('company', ''),
            location=job_data.get('location', ''),
            url=job_data.get('url', ''),
            source='Manual',
            description=job_data.get('description', '')
        )
        
        # Score job
        match_result = self.scorer.score_job(job)
        
        # Prepare data
        data = {
            'job_id': job.job_id,
            'date_found': datetime.now().strftime('%Y-%m-%d'),
            'company': job.company,
            'title': job.title,
            'location': job.location,
            'url': job.url,
            'source': 'Manual',
            'match_status': match_result.status.value,
            'match_score': match_result.score,
            'match_reasons': ' | '.join(match_result.reasons),
            'matched_skills': ', '.join(match_result.matched_skills),
        }
        
        # Add to sheets
        self.sheets_manager.add_job(data)
        
        return match_result
    
    def test_collectors(self):
        """Test all collectors with a sample run"""
        logger.info("Testing collectors...")
        
        for company in self.companies[:3]:  # Test first 3
            ats = company.get('ats', '')
            if ats not in ['greenhouse', 'lever', 'smartrecruiters']:
                continue
            
            logger.info(f"\n📊 Testing: {company['name']}")
            
            try:
                collector = self._get_collector(company)
                if collector:
                    jobs = collector.fetch_jobs()
                    logger.info(f"   ✅ Found {len(jobs)} jobs")
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
    
    def test_scorer(self):
        """Test the scoring engine"""
        logger.info("Testing scorer...")
        
        # Create test job
        test_job = Job(
            job_id="test_001",
            title="ERP Business Analyst",
            company="Test Company",
            location="Jakarta",
            url="https://example.com/job",
            source="Test",
            description="Looking for SAP ECC expert with SQL and Excel skills."
        )
        
        result = self.scorer.score_job(test_job)
        
        logger.info(f"\nTest Result: {result.status.value} ({result.score}/100)")
        logger.info(f"Reasons: {result.reasons}")
        logger.info(f"Matched Skills: {result.matched_skills}")


def main():
    """Main entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Job Intelligence Platform')
    parser.add_argument('--config', '-c', default='config', help='Config directory path')
    parser.add_argument('--test-collectors', action='store_true', help='Test collectors only')
    parser.add_argument('--test-scorer', action='store_true', help='Test scorer only')
    parser.add_argument('--force-email', action='store_true', help='Force email notification')
    parser.add_argument('--dry-run', action='store_true', help='Run without saving to sheets')
    
    args = parser.parse_args()
    
    try:
        # Initialize platform
        platform = JobIntelligencePlatform(config_dir=args.config)
        
        # Run requested action
        if args.test_collectors:
            platform.test_collectors()
        elif args.test_scorer:
            platform.test_scorer()
        else:
            result = platform.run(force_email=args.force_email)
            
            # Print result summary
            print("\n" + "=" * 40)
            print("RUN COMPLETE")
            print("=" * 40)
            print(f"Total Jobs: {result['total_jobs']}")
            print(f"YES Matches: {result['yes_matches']}")
            print(f"MAYBE Matches: {result['maybe_matches']}")
            print(f"New Jobs Added: {result['new_jobs']}")
            print(f"Duration: {result['duration_seconds']:.1f}s")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()