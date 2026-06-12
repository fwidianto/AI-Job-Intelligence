"""
Job Intelligence Platform - Main Entry Point

Phase 2: Focus on job discovery at scale
- ATS auto-detection
- Generic scraper fallback
- Job board integration
- Daily intelligence mode
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.collectors import (
    CollectorFactory,
    Job,
    CollectorError,
    GreenhouseCollector,
    LeverCollector,
    SmartRecruitersCollector,
    ICimsCollector,
    WorkdayExtractor,
    SuccessFactorsExtractor,
    JobSourceResolver,
    JobIntelligenceEngine,
    ProfileConfig,
)
from src.scorer import JobScorer, MatchResult, MatchStatus
from src.sheets import SheetConfig, create_sheets_manager, MockSheetsManager
from src.notifier import create_notifier, MockEmailNotifier
from src.utils import safe_text
from src.detectors.ats_detector import ATSDetector, detect_ats

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(logs_dir, exist_ok=True)


class EmojiFilter(logging.Filter):
    """Filter that removes emojis from log messages"""
    EMOJI_MAP = {
        '📊': '[INFO]', '✅': '[OK]', '❌': '[ERROR]', '⚠️': '[WARN]',
        '⏭️': '[SKIP]', '⏱️': '[TIME]', '🔍': '[SEARCH]', '📧': '[EMAIL]',
        '📋': '[LIST]', '📝': '[NOTE]', '⭐': '[STAR]', '🔥': '[HOT]',
        '💼': '[JOB]', '🏢': '[COMPANY]', '📍': '[LOCATION]', '💰': '[SALARY]',
    }
    
    def filter(self, record):
        # Only convert string messages
        if isinstance(record.msg, str):
            record.msg = safe_text(record.msg)
        # Don't convert args - let logging handle formatting
        return True


# Configure logging with emoji filter
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[]
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.addFilter(EmojiFilter())
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)

# File handler
file_handler = logging.FileHandler(os.path.join(logs_dir, 'job_intelligence.log'), mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.addFilter(EmojiFilter())
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)

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
        
        Phase 2: Focus on job discovery at scale.
        """
        logger.info("=" * 60)
        logger.info("Starting Job Intelligence Platform")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        all_jobs = []
        errors = []
        
        # Phase 2: Collect from job boards first (broad coverage)
        logger.info("[PHASE 2] Collecting from job boards...")
        board_jobs = self._collect_from_job_boards()
        all_jobs.extend(board_jobs)
        logger.info("[BOARD] Collected %d jobs from job boards", len(board_jobs))
        
        # Phase 2: Collect from company career pages with auto-detection
        logger.info("[PHASE 2] Collecting from company career pages...")
        company_jobs = self._collect_from_companies()
        all_jobs.extend(company_jobs)
        logger.info("[COMPANY] Collected %d jobs from company pages", len(company_jobs))
        
        # Score all jobs
        logger.info("[SCORING] Scoring %d jobs...", len(all_jobs))
        scored_jobs = []
        for item in all_jobs:
            job = item['job'] if isinstance(item, dict) else item
            match_result = self.scorer.score_job(job)
            job.match_score = match_result.score
            
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
            
            scored_jobs.append({
                'job': job,
                'result': match_result,
                'data': job_data
            })
            
            # Log high matches
            if match_result.status == MatchStatus.YES and match_result.score >= 75:
                logger.info("[MATCH] %s at %s (%d/100)", 
                          job.title, job.company, int(match_result.score))
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        
        yes_matches = [j for j in scored_jobs if j['result'].status == MatchStatus.YES]
        maybe_matches = [j for j in scored_jobs if j['result'].status == MatchStatus.MAYBE]
        
        logger.info("Total jobs collected: %d", len(scored_jobs))
        logger.info("YES matches: %d", len(yes_matches))
        logger.info("MAYBE matches: %d", len(maybe_matches))
        
        if errors:
            logger.warning("Errors encountered: %d", len(errors))
        
        # Store in Google Sheets
        new_jobs = self._store_jobs(scored_jobs)
        logger.info("New jobs added to sheet: %d", new_jobs)
        
        # Send email notification
        high_matches = [j for j in scored_jobs if j['result'].score >= 75 and j['result'].status == MatchStatus.YES]
        
        if high_matches or force_email:
            job_dicts = [j['data'] for j in high_matches]
            if job_dicts:
                self.notifier.send_job_alert(job_dicts)
                logger.info("Sent email with %d high-priority matches", len(high_matches))
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("Completed in %.1f seconds", duration)
        logger.info("=" * 60)
        
        return {
            'total_jobs': len(scored_jobs),
            'yes_matches': len(yes_matches),
            'maybe_matches': len(maybe_matches),
            'new_jobs': new_jobs,
            'errors': len(errors),
            'duration_seconds': duration
        }
    
    def run_daily(self):
        """
        Run daily intelligence mode.
        
        Focus: Discover relevant analyst jobs at scale.
        Output: Clean list of relevant jobs with scores.
        """
        logger.info("=" * 60)
        logger.info("DAILY INTELLIGENCE MODE")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        all_jobs = []
        
        # 1. Collect from job boards
        logger.info("[STEP 1] Collecting from job boards...")
        try:
            board_jobs = collect_from_all_boards()
            logger.info("Found %d jobs from job boards", len(board_jobs))
            all_jobs.extend(board_jobs)
        except Exception as e:
            logger.error("Job board collection failed: %s", str(e))
        
        # 2. Collect from companies with auto-detection
        logger.info("[STEP 2] Collecting from company career pages...")
        for company in self.companies:
            name = company.get('name', 'Unknown')
            url = company.get('career_url', '')
            
            if not url:
                continue
            
            try:
                # Auto-detect ATS
                detection = detect_ats(url)
                ats = detection['ats']
                
                if ats == 'custom' or detection['confidence'] < 0.7:
                    # Use generic scraper for custom sites
                    logger.info("[SCRAP] %s: Using generic scraper", name)
                    scraper = GenericScraper(name, url, company)
                    jobs = scraper.fetch_jobs()
                else:
                    # Use factory to create correct collector
                    logger.info("[COLLECT] %s: Detected %s", name, ats)
                    collector = CollectorFactory.create(url, name, company)
                    if collector:
                        jobs = collector.fetch_jobs()
                    else:
                        jobs = []
                
                all_jobs.extend(jobs)
                logger.info("[OK] %s: %d jobs", name, len(jobs))
                
            except Exception as e:
                logger.warning("[FAIL] %s: %s", name, str(e)[:60])
        
        # 3. Score all jobs
        logger.info("[STEP 3] Scoring %d jobs...", len(all_jobs))
        
        scored_jobs = []
        for job in all_jobs:
            result = self.scorer.score_job(job)
            job.match_score = result.score
            scored_jobs.append((job, result))
        
        # 4. Sort by score (highest first)
        scored_jobs.sort(key=lambda x: x[1].score, reverse=True)
        
        # 5. Print daily report
        print("\n" + "=" * 80)
        print("DAILY INTELLIGENCE REPORT")
        print("=" * 80)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"Total jobs discovered: {len(scored_jobs)}")
        print("-" * 80)
        
        # Show top jobs
        top_jobs = [j for j in scored_jobs if j[1].status == MatchStatus.YES]
        
        print(f"\nRELEVANT JOBS (YES matches): {len(top_jobs)}")
        print("-" * 80)
        
        for i, (job, result) in enumerate(top_jobs[:30], 1):
            print(f"\n{i}. {job.title}")
            print(f"   Company: {job.company}")
            print(f"   Location: {job.location}")
            print(f"   Score: {int(result.score)}/100")
            print(f"   URL: {job.url}")
            if result.matched_skills:
                print(f"   Skills: {', '.join(result.matched_skills[:5])}")
        
        # Show maybe matches
        maybe_jobs = [j for j in scored_jobs if j[1].status == MatchStatus.MAYBE]
        
        print(f"\n\nMAYBE RELEVANT: {len(maybe_jobs)}")
        print("-" * 80)
        
        for i, (job, result) in enumerate(maybe_jobs[:20], 1):
            print(f"{i}. {job.title} at {job.company} ({int(result.score)}/100)")
        
        # 6. Store in sheets
        job_dicts = []
        for job, result in scored_jobs:
            job_dicts.append({
                'job_id': job.job_id,
                'date_found': datetime.now().strftime('%Y-%m-%d'),
                'company': job.company,
                'title': job.title,
                'location': job.location,
                'url': job.url,
                'source': job.source,
                'match_status': result.status.value,
                'match_score': int(result.score),
                'match_reasons': ' | '.join(result.reasons),
                'matched_skills': ', '.join(result.matched_skills),
            })
        
        new_count = self._store_jobs([{'job': j, 'result': r, 'data': d} 
                                     for (j, r), d in zip(scored_jobs, job_dicts)])
        
        # 7. Summary
        duration = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print("DAILY SUMMARY")
        print("=" * 80)
        print(f"Total jobs discovered: {len(scored_jobs)}")
        print(f"Relevant (YES): {len(top_jobs)}")
        print(f"Maybe relevant: {len(maybe_jobs)}")
        print(f"New jobs added to sheet: {new_count}")
        print(f"Duration: {duration:.1f} seconds")
        print("=" * 80)
        
        return {
            'total_jobs': len(scored_jobs),
            'yes_matches': len(top_jobs),
            'maybe_matches': len(maybe_jobs),
            'new_jobs': new_count,
            'duration_seconds': duration
        }
    
    def _collect_from_job_boards(self) -> List[Job]:
        """Collect jobs from all job boards"""
        jobs = []
        try:
            jobs.extend(collect_from_all_boards())
        except Exception as e:
            logger.error("Failed to collect from job boards: %s", str(e))
        return jobs
    
    def _collect_from_companies(self) -> List[Job]:
        """Collect jobs from companies with auto-detection"""
        jobs = []
        
        for company in self.companies:
            name = company.get('name', 'Unknown')
            url = company.get('career_url', '')
            
            if not url:
                continue
            
            try:
                detection = detect_ats(url)
                ats = detection['ats']
                
                if ats == 'custom':
                    scraper = GenericScraper(name, url, company)
                    jobs.extend(scraper.fetch_jobs())
                else:
                    collector = CollectorFactory.create(url, name, company)
                    if collector:
                        jobs.extend(collector.fetch_jobs())
                        
            except Exception as e:
                logger.debug("Failed for %s: %s", name, str(e))
        
        return jobs
    
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
            name = company.get('name', 'Unknown')
            if ats not in ['greenhouse', 'lever', 'smartrecruiters']:
                continue
            
            logger.info("[TEST] Company: %s (ATS: %s)", name, ats)
            
            try:
                collector = self._get_collector(company)
                if collector:
                    jobs = collector.fetch_jobs()
                    logger.info("[OK] Found %d jobs", len(jobs))
            except Exception as e:
                logger.error("[ERROR] %s: %s", name, str(e))
    
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
        
        # Convert score to int for logging
        score_int = int(result.score) if result.score else 0
        
        logger.info("Test Result: %s (%d/100)", result.status.value, score_int)
        logger.info("Reasons: %s", result.reasons)
        logger.info("Matched Skills: %s", result.matched_skills)
    
    def validate_companies(self):
        """Validate company configurations and report issues"""
        from src.utils import validate_company_config
        
        print("\n" + "=" * 80)
        print("COMPANY CONFIGURATION VALIDATION REPORT")
        print("=" * 80)
        print(f"{'Company':<30} {'ATS':<15} {'Status':<12} {'Issue'}")
        print("-" * 80)
        
        working = []
        broken = []
        manual = []
        unverified = []
        
        for company in self.companies:
            result = validate_company_config(company)
            
            name = result['name'][:28]
            ats = result['ats']
            status = result['status']
            issue = result['issues'][0] if result['issues'] else ''
            
            print(f"{name:<30} {ats:<15} {status:<12} {issue}")
            
            if status == 'working':
                working.append(result)
            elif status == 'broken':
                broken.append(result)
            elif status == 'manual':
                manual.append(result)
            else:
                unverified.append(result)
        
        print("-" * 80)
        print("\nSUMMARY:")
        print(f"  Working (auto):     {len(working)}")
        print(f"  Broken (needs fix): {len(broken)}")
        print(f"  Manual (no auto):  {len(manual)}")
        print(f"  Unverified:         {len(unverified)}")
        print(f"  Total:             {len(self.companies)}")
        
        if broken:
            print("\n" + "=" * 80)
            print("RECOMMENDATIONS FOR BROKEN CONFIGURATIONS:")
            print("=" * 80)
            for result in broken:
                print(f"\n{result['name']}:")
                for rec in result['recommendations']:
                    print(f"  - {rec}")


def main():
    """Main entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Job Intelligence Platform')
    parser.add_argument('--config', '-c', default='config', help='Config directory path')
    parser.add_argument('--daily', action='store_true', help='Run daily intelligence mode')
    parser.add_argument('--test-collectors', action='store_true', help='Test collectors only')
    parser.add_argument('--test-scorer', action='store_true', help='Test scorer only')
    parser.add_argument('--validate-companies', action='store_true', help='Validate company configurations')
    parser.add_argument('--detect-ats', metavar='URL', help='Detect ATS for a URL')
    parser.add_argument('--force-email', action='store_true', help='Force email notification')
    parser.add_argument('--dry-run', action='store_true', help='Run without saving to sheets')
    
    args = parser.parse_args()
    
    try:
        # Handle ATS detection
        if args.detect_ats:
            result = detect_ats(args.detect_ats)
            print("\n" + "=" * 60)
            print("ATS DETECTION RESULT")
            print("=" * 60)
            print(f"URL: {args.detect_ats}")
            print(f"Detected ATS: {result['ats']}")
            print(f"Confidence: {result['confidence']:.2f}")
            print(f"Company Slug: {result['company_slug']}")
            if result['api_url']:
                print(f"API URL: {result['api_url']}")
            return
        
        # Initialize platform
        platform = JobIntelligencePlatform(config_dir=args.config)
        
        # Run requested action
        if args.validate_companies:
            platform.validate_companies()
        elif args.daily:
            platform.run_daily()
        elif args.test_collectors:
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
        logger.error("Fatal error: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()