"""
Job Intelligence Engine - Main Orchestrator

This module provides the central orchestration for the job intelligence system.

Architecture:
1. API-FIRST: Use Greenhouse, Lever, SmartRecruiters APIs
2. SEARCH-BASED: Use DuckDuckGo/Google search for discovery
3. SCRAPING-LAST-RESORT: Only for stable job listing pages

Pipeline:
1. Load user profile
2. Discover jobs from multiple sources
3. Normalize and deduplicate
4. Score against profile
5. Deliver matches
"""

import logging
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import Job
from .factory import CollectorFactory
from .source_resolver import JobSourceResolver
from .search_discovery import SearchJobDiscovery, search_jobs, search_company_jobs
from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .smartrecruiters import SmartRecruitersCollector

logger = logging.getLogger(__name__)


@dataclass
class ProfileConfig:
    """User profile configuration"""
    target_roles: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    salary_min: int = 0
    salary_max: int = 0
    excluded_roles: List[str] = field(default_factory=list)
    excluded_companies: List[str] = field(default_factory=list)


@dataclass
class JobSource:
    """A job source with metadata"""
    name: str
    source_type: str  # 'api', 'search', 'scraper'
    url: str
    company: str
    jobs_found: int = 0
    success: bool = False
    error: Optional[str] = None
    time_taken: float = 0.0


@dataclass
class IngestionResult:
    """Result of job ingestion from all sources"""
    total_jobs: int = 0
    unique_jobs: int = 0
    sources: List[JobSource] = field(default_factory=list)
    jobs: List[Job] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Complete pipeline result"""
    success: bool
    jobs_ingested: int = 0
    jobs_scored: int = 0
    yes_matches: int = 0
    maybe_matches: int = 0
    no_matches: int = 0
    jobs: List[Job] = field(default_factory=list)
    ingestion: IngestionResult = None
    duration_seconds: float = 0.0
    error: Optional[str] = None


class JobIntelligenceEngine:
    """
    Main orchestrator for the Job Intelligence Platform.
    
    This engine implements the new architecture:
    - API-FIRST job discovery
    - SEARCH-BASED job discovery
    - SCRAPING-LAST-RESORT
    
    Usage:
        engine = JobIntelligenceEngine(profile_config)
        result = engine.run_pipeline()
        
        for job in result.jobs:
            if job.match_status == 'YES':
                print(f"Match: {job.title} at {job.company}")
    """
    
    # Known company API endpoints (Indonesian companies)
    KNOWN_API_COMPANIES = {
        'grab': {
            'ats': 'lever',
            'api_url': 'https://api.lever.co/v0/postings/grab?mode=json',
            'slug': 'grab'
        },
        'shopee': {
            'ats': 'smartrecruiters',
            'api_url': None,  # SuccessFactors - no public API
            'slug': 'shopee'
        },
        'goto': {
            'ats': 'workday',
            'api_url': None,
            'slug': 'goto'
        },
        'gojek': {
            'ats': 'greenhouse',
            'api_url': None,
            'slug': 'gojek'
        },
    }
    
    def __init__(self, profile: ProfileConfig):
        self.profile = profile
        self.scorer = None  # Will be initialized with scoring config
        self._init_scorer()
    
    def _init_scorer(self):
        """Initialize the scoring engine"""
        from ..scorer import JobScorer
        
        scoring_config = {
            'target_roles': self.profile.target_roles,
            'skills': self.profile.skills,
            'locations': self.profile.locations,
            'salary_min': self.profile.salary_min,
            'salary_max': self.profile.salary_max,
            'excluded_roles': self.profile.excluded_roles,
            'scoring': {
                'yes_threshold': 70,
                'maybe_threshold': 50
            }
        }
        
        self.scorer = JobScorer(scoring_config)
    
    def run_pipeline(self) -> PipelineResult:
        """
        Run the complete job intelligence pipeline.
        
        Steps:
        1. Discover jobs from all sources
        2. Normalize and deduplicate
        3. Score against profile
        4. Return matched jobs
        
        Returns:
            PipelineResult with matched jobs
        """
        start_time = time.time()
        
        try:
            logger.info("=" * 60)
            logger.info("JOB INTELLIGENCE ENGINE - STARTING PIPELINE")
            logger.info("=" * 60)
            
            # Step 1: Ingest jobs from all sources
            ingestion = self._ingest_jobs()
            logger.info(f"Ingestion complete: {ingestion.total_jobs} jobs from {len(ingestion.sources)} sources")
            
            # Step 2: Normalize and deduplicate
            jobs = self._normalize_jobs(ingestion.jobs)
            logger.info(f"Normalization complete: {len(jobs)} unique jobs")
            
            # Step 3: Score jobs
            scored_jobs = self._score_jobs(jobs)
            logger.info(f"Scoring complete: {len(scored_jobs)} jobs scored")
            
            # Calculate statistics
            yes_count = sum(1 for j in scored_jobs if j.match_status == 'YES')
            maybe_count = sum(1 for j in scored_jobs if j.match_status == 'MAYBE')
            no_count = sum(1 for j in scored_jobs if j.match_status == 'NO')
            
            duration = time.time() - start_time
            
            logger.info("=" * 60)
            logger.info(f"PIPELINE COMPLETE: {duration:.1f}s")
            logger.info(f"  Ingested: {ingestion.total_jobs}")
            logger.info(f"  Unique: {len(jobs)}")
            logger.info(f"  YES: {yes_count}, MAYBE: {maybe_count}, NO: {no_count}")
            logger.info("=" * 60)
            
            return PipelineResult(
                success=True,
                jobs_ingested=ingestion.total_jobs,
                jobs_scored=len(scored_jobs),
                yes_matches=yes_count,
                maybe_matches=maybe_count,
                no_matches=no_count,
                jobs=scored_jobs,
                ingestion=ingestion,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            return PipelineResult(
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time
            )
    
    def _ingest_jobs(self) -> IngestionResult:
        """
        Ingest jobs from all available sources.
        
        Priority:
        1. API-based collectors (Greenhouse, Lever, SmartRecruiters)
        2. Search-based discovery
        3. Company-specific sources
        """
        result = IngestionResult()
        all_jobs = []
        
        # Step 1: API-based collection (fastest, most reliable)
        api_results = self._ingest_from_apis()
        for source in api_results:
            result.sources.append(source)
            all_jobs.extend(source.jobs if hasattr(source, 'jobs') else [])
        
        # Step 2: Search-based discovery
        search_results = self._ingest_from_search()
        for source in search_results:
            result.sources.append(source)
            all_jobs.extend(source.jobs if hasattr(source, 'jobs') else [])
        
        # Step 3: Company-specific sources
        company_results = self._ingest_from_companies()
        for source in company_results:
            result.sources.append(source)
            all_jobs.extend(source.jobs if hasattr(source, 'jobs') else [])
        
        result.total_jobs = sum(s.jobs_found for s in result.sources)
        result.jobs = all_jobs
        
        return result
    
    def _ingest_from_apis(self) -> List[JobSource]:
        """Ingest jobs using public APIs"""
        sources = []
        
        # Target companies with known APIs
        api_targets = [
            {
                'name': 'Grab',
                'company': 'Grab',
                'ats': 'lever',
                'slug': 'grab',
                'api_url': 'https://api.lever.co/v0/postings/grab?mode=json'
            },
            {
                'name': 'Unilever Greenhouse',
                'company': 'Unilever',
                'ats': 'greenhouse',
                'slug': 'unilever',
                'api_url': 'https://boards-api.greenhouse.io/v1/boards/unilever/jobs'
            },
        ]
        
        for target in api_targets:
            source = JobSource(
                name=target['name'],
                source_type='api',
                url=target['api_url'],
                company=target['company']
            )
            
            start_time = time.time()
            try:
                if target['ats'] == 'lever':
                    collector = LeverCollector(
                        company_name=target['company'],
                        company_slug=target['slug']
                    )
                elif target['ats'] == 'greenhouse':
                    collector = GreenhouseCollector(
                        company_name=target['company'],
                        company_slug=target['slug']
                    )
                else:
                    continue
                
                jobs = collector.fetch_jobs()
                source.jobs_found = len(jobs)
                source.success = len(jobs) > 0
                
            except Exception as e:
                source.error = str(e)
                logger.warning(f"API collection failed for {target['name']}: {e}")
            finally:
                source.time_taken = time.time() - start_time
            
            sources.append(source)
        
        return sources
    
    def _ingest_from_search(self) -> List[JobSource]:
        """Ingest jobs using search-based discovery"""
        sources = []
        
        # Search queries based on profile
        search_queries = []
        
        for role in self.profile.target_roles[:3]:
            for location in self.profile.locations[:2]:
                search_queries.append(f"{role} {location} jakarta 2024")
        
        # Add company-specific searches
        for company in ['Grab', 'Shopee', 'GoTo', 'Unilever', 'Astra']:
            search_queries.append(f"{company} career {self.profile.target_roles[0] if self.profile.target_roles else 'analyst'}")
        
        # Remove duplicates
        search_queries = list(set(search_queries))[:10]
        
        for query in search_queries:
            source = JobSource(
                name=f"Search: {query}",
                source_type='search',
                url=f"search://{query}",
                company='Multiple'
            )
            
            start_time = time.time()
            try:
                discovery = SearchJobDiscovery()
                result = discovery.search(query, max_results=10)
                
                if result.success:
                    source.jobs_found = len(result.jobs)
                    source.success = True
                    
                    # Convert SearchResult to Job
                    jobs = []
                    for sr in result.jobs:
                        job = Job(
                            id=sr.url,
                            title=sr.title,
                            company=sr.company or source.company,
                            location=sr.location,
                            url=sr.url,
                            source='search',
                            description=sr.snippet
                        )
                        jobs.append(job)
                    source.jobs = jobs  # type: ignore
                else:
                    source.error = result.error
                    
            except Exception as e:
                source.error = str(e)
            finally:
                source.time_taken = time.time() - start_time
            
            sources.append(source)
        
        return sources
    
    def _ingest_from_companies(self) -> List[JobSource]:
        """Ingest jobs from specific company sources"""
        sources = []
        
        # Target companies
        companies = [
            {'name': 'Grab', 'url': 'https://grab.careers', 'ats': 'lever'},
            {'name': 'Shopee', 'url': 'https://www.shopee.co.id/careers', 'ats': 'successfactors'},
            {'name': 'GoTo', 'url': 'https://www.goto.com/careers', 'ats': 'workday'},
            {'name': 'Unilever', 'url': 'https://www.unilever.com/careers', 'ats': 'custom'},
        ]
        
        for company in companies:
            source = JobSource(
                name=company['name'],
                source_type='company',
                url=company['url'],
                company=company['name']
            )
            
            start_time = time.time()
            try:
                # Use JobSourceResolver for intelligent source detection
                resolver = JobSourceResolver()
                result = resolver.resolve(company['url'], company['name'])
                
                if result.success:
                    source.jobs_found = len(result.jobs)
                    source.success = True
                    source.jobs = result.jobs  # type: ignore
                else:
                    source.error = result.error or "No jobs found"
                    
            except Exception as e:
                source.error = str(e)
            finally:
                source.time_taken = time.time() - start_time
            
            sources.append(source)
        
        return sources
    
    def _normalize_jobs(self, jobs: List[Job]) -> List[Job]:
        """
        Normalize and deduplicate jobs.
        
        Steps:
        1. Remove duplicates by URL
        2. Standardize titles
        3. Validate required fields
        """
        seen_urls = {}
        unique_jobs = []
        
        for job in jobs:
            # Skip if no title or URL
            if not job.title or not job.url:
                continue
            
            # Deduplicate by URL
            if job.url in seen_urls:
                # Keep the one with more description
                existing = seen_urls[job.url]
                if len(job.description or '') > len(existing.description or ''):
                    unique_jobs.remove(existing)
                    unique_jobs.append(job)
                    seen_urls[job.url] = job
            else:
                # Normalize title
                job.title = self._normalize_title(job.title)
                
                # Set default location
                if not job.location:
                    job.location = 'Indonesia'
                
                seen_urls[job.url] = job
                unique_jobs.append(job)
        
        return unique_jobs
    
    def _normalize_title(self, title: str) -> str:
        """Normalize job title"""
        if not title:
            return 'Unknown'
        
        # Remove extra whitespace
        title = ' '.join(title.split())
        
        # Remove common suffixes
        for suffix in [' (Open)', ' - Apply Now', ' | Careers']:
            if title.endswith(suffix):
                title = title[:-len(suffix)]
        
        return title.strip()
    
    def _score_jobs(self, jobs: List[Job]) -> List[Job]:
        """Score jobs against user profile"""
        scored_jobs = []
        
        for job in jobs:
            try:
                result = self.scorer.score_job(job)
                job.match_score = result.score
                job.match_status = result.status.value
                job.match_reasons = result.reasons
                job.matched_skills = result.matched_skills
                scored_jobs.append(job)
            except Exception as e:
                logger.debug(f"Scoring failed for {job.title}: {e}")
                # Assign default score
                job.match_score = 50
                job.match_status = 'NO'
                job.match_reasons = ['Scoring failed']
                scored_jobs.append(job)
        
        # Sort by match score (highest first)
        scored_jobs.sort(key=lambda j: j.match_score, reverse=True)
        
        return scored_jobs
    
    def get_yes_matches(self) -> List[Job]:
        """Get only YES matches from last run"""
        return [j for j in self.jobs if j.match_status == 'YES']
    
    def get_maybe_matches(self) -> List[Job]:
        """Get only MAYBE matches from last run"""
        return [j for j in self.jobs if j.match_status == 'MAYBE']
    
    def get_match_summary(self) -> Dict[str, Any]:
        """Get summary of matches"""
        yes = self.get_yes_matches()
        maybe = self.get_maybe_matches()
        no = [j for j in self.jobs if j.match_status == 'NO']
        
        return {
            'total_jobs': len(self.jobs),
            'yes_count': len(yes),
            'maybe_count': len(maybe),
            'no_count': len(no),
            'match_rate': (len(yes) + len(maybe)) / len(self.jobs) * 100 if self.jobs else 0,
            'top_yes_matches': [
                {'title': j.title, 'company': j.company, 'score': j.match_score}
                for j in yes[:5]
            ]
        }


def run_job_intelligence(profile: Dict) -> PipelineResult:
    """
    Convenience function to run the job intelligence pipeline.
    
    Usage:
        profile = {
            'target_roles': ['ERP Analyst', 'Business Analyst'],
            'skills': ['SAP', 'SQL', 'Excel'],
            'locations': ['Jakarta', 'Remote'],
            'salary_min': 15000000,
            'salary_max': 25000000,
        }
        
        result = run_job_intelligence(profile)
        
        for job in result.jobs:
            if job.match_status == 'YES':
                print(f"Match: {job.title}")
    """
    profile_config = ProfileConfig(
        target_roles=profile.get('target_roles', []),
        skills=profile.get('skills', []),
        locations=profile.get('locations', []),
        salary_min=profile.get('salary_min', 0),
        salary_max=profile.get('salary_max', 0),
        excluded_roles=profile.get('excluded_roles', []),
        excluded_companies=profile.get('excluded_companies', [])
    )
    
    engine = JobIntelligenceEngine(profile_config)
    return engine.run_pipeline()