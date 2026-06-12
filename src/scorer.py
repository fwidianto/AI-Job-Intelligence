"""
Job Scoring Engine - Evaluates job opportunities against user profile

Simple rule-based matching with YES/MAYBE/NO classification.
Designed to be maintainable and easy to adjust.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class MatchStatus(Enum):
    """Job match classification"""
    YES = "YES"      # Apply immediately
    MAYBE = "MAYBE"  # Review and decide
    NO = "NO"        # Skip


@dataclass
class MatchResult:
    """Result of job matching against user profile"""
    
    status: MatchStatus
    score: int  # 0-100
    reasons: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    role_match: str = ""
    location_match: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'status': self.status.value,
            'score': self.score,
            'reasons': ' | '.join(self.reasons),
            'matched_skills': ', '.join(self.matched_skills),
            'missing_skills': ', '.join(self.missing_skills),
            'role_match': self.role_match,
            'location_match': 'Yes' if self.location_match else 'No',
        }
    
    def __str__(self) -> str:
        return f"{self.status.value} ({self.score}/100): {', '.join(self.reasons[:3])}"


class JobScorer:
    """
    Scores job opportunities against user profile.
    
    Uses simple rule-based matching with configurable weights.
    """
    
    # Role matching keywords (expanded for Indonesian market)
    ROLE_KEYWORDS = {
        # Exact matches (highest priority)
        'exact': [
            # Core analyst roles
            'erp analyst', 'business analyst', 'operations analyst',
            'cost control analyst', 'finance analyst', 'financial analyst',
            'reporting analyst', 'data analyst', 'bi analyst', 'bi specialist',
            'process analyst', 'systems analyst', 'functional analyst',
            'sap analyst', 'odoo analyst', 'erp consultant', 'erp specialist',
            'business intelligence analyst', 'budget analyst',
            # Extended matches (still high relevance)
            'financial planning analyst', 'management reporting analyst',
            'cost analyst', 'pricing analyst', 'treasury analyst',
            'supply chain analyst', 'procurement analyst',
            'performance analyst', 'kpi analyst', 'metrics analyst',
            'business intelligence specialist', 'bi developer',
            'sql analyst', 'reporting specialist', 'dashboard analyst',
        ],
        # Related matches (medium priority)
        'related': [
            'analyst', 'specialist', 'coordinator', 'administrator',
            'consultant', 'executive', 'officer', 'controller',
            'associate', 'junior', 'senior', 'lead', 'principal',
            'manager', 'supervisor', 'assistant',
            'implementation', 'support', 'technical',
        ],
        # Keywords that indicate NOT relevant
        'exclude': [
            'senior manager', 'director', 'vp ', 'head of',
            'software engineer', 'developer', 'programmer',
            'marketing', 'sales', 'hr ', 'human resources',
            'legal', 'attorney', 'lawyer', 'recruiter',
            'intern', 'internship', 'junior developer', 'trainee',
        ]
    }
    
    # Skills to look for (case-insensitive)
    SKILL_KEYWORDS = [
        # ERP Systems
        'SAP', 'SAP ECC', 'SAP S/4HANA', 'Odoo', 'ERP', 'Oracle', 'Oracle ERP',
        'Workday', 'PeopleSoft', 'Dynamics', 'Infor',
        
        # BI & Analytics
        'SQL', 'Power BI', 'Tableau', 'Looker', 'Looker Studio',
        'Business Intelligence', 'BI Tools', 'Data Visualization',
        'Dashboard', 'Reporting', 'Crystal Reports', 'SSRS',
        
        # Finance
        'Budgeting', 'Forecasting', 'Cost Control', 'Costing',
        'Financial Reporting', 'Management Reporting',
        'Finance', 'Accounting', 'Tax',
        
        # Tools
        'Excel', 'Google Sheets', 'Python', 'VBA', 'Macro',
        'ETL', 'Data Integration', 'API',
        
        # Soft skills
        'Process Improvement', 'Requirements Analysis',
        'Stakeholder Management', 'Project Management',
        'Documentation', 'Training', 'Support',
    ]
    
    # Location keywords
    LOCATION_KEYWORDS = [
        'jakarta', 'jabotabek', 'greater jakarta',
        'bekasi', 'karawang', 'bandung', 'surabaya',
        'remote', 'work from home', 'wfh', 'hybrid',
    ]
    
    def __init__(self, user_profile: Dict[str, Any]):
        """
        Initialize scorer with user profile.
        
        Args:
            user_profile: Dictionary containing target roles, skills, locations
        """
        self.target_roles = [r.lower() for r in user_profile.get('target_roles', [])]
        self.target_skills = [s.lower() for s in user_profile.get('skills', [])]
        self.target_locations = [l.lower() for l in user_profile.get('locations', [])]
        self.salary_min = user_profile.get('salary_min', 0)
        self.salary_max = user_profile.get('salary_max', 999999999)
        
        # Scoring thresholds (lowered for higher recall)
        self.yes_threshold = user_profile.get('scoring', {}).get('yes_threshold', 60)
        self.maybe_threshold = user_profile.get('scoring', {}).get('maybe_threshold', 40)
        
        self.logger = logging.getLogger(__name__)
    
    def score_job(self, job) -> MatchResult:
        """
        Score a job against the user profile.
        
        Args:
            job: Job object with title, description, location, etc.
            
        Returns:
            MatchResult with status, score, and reasons
        """
        reasons = []
        matched_skills = []
        missing_skills = []
        role_match = ""
        location_match = False
        
        # ===== 1. ROLE MATCHING (30 points) =====
        role_score, role_reason, role_type = self._match_role(job.title)
        reasons.append(role_reason)
        role_match = role_type
        
        # ===== 2. SKILLS MATCHING (40 points) =====
        skills_score, matched, missing = self._match_skills(job.description, job.skills)
        matched_skills = matched
        missing_skills = missing
        reasons.append(f"Skills: {len(matched)}/{len(self.target_skills)} matched")
        
        # ===== 3. LOCATION MATCHING (15 points) =====
        location_score, location_reason = self._match_location(job.location)
        reasons.append(location_reason)
        location_match = location_score > 0
        
        # ===== 4. SALARY CHECK (15 points) =====
        salary_score, salary_reason = self._check_salary(job.salary_min, job.salary_max)
        reasons.append(salary_reason)
        
        # ===== 5. COMPANY MATCH (Bonus 5 points) =====
        company_score = 5  # Basic bonus for all companies
        
        
        # ===== CALCULATE TOTAL SCORE =====
        total_score = role_score + skills_score + location_score + salary_score + company_score
        
        # Cap at 100
        total_score = min(total_score, 100)
        
        # ===== DETERMINE STATUS =====
        if total_score >= self.yes_threshold:
            status = MatchStatus.YES
        elif total_score >= self.maybe_threshold:
            status = MatchStatus.MAYBE
        else:
            status = MatchStatus.NO
        
        # Add warning for low skill matches
        if len(matched_skills) == 0 and role_score > 0:
            reasons.append("⚠️ No specific skills matched - review requirements carefully")
        
        return MatchResult(
            status=status,
            score=total_score,
            reasons=reasons,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            role_match=role_match,
            location_match=location_match
        )
    
    def _match_role(self, title: str) -> tuple:
        """
        Match job title against target roles.
        
        Returns:
            (score, reason, match_type)
        """
        title_lower = title.lower()
        
        # Check exact matches first
        for role in self.target_roles:
            if role in title_lower:
                # Check if it's not an exclusion
                for exclude in self.ROLE_KEYWORDS['exclude']:
                    if exclude in title_lower:
                        return 0, f"❌ Role excluded: {title}", "excluded"
                
                return 30, f"✅ Exact role match: {title}", "exact"
        
        # Check related matches
        for keyword in self.ROLE_KEYWORDS['related']:
            if keyword in title_lower:
                # Check for exclusions
                for exclude in self.ROLE_KEYWORDS['exclude']:
                    if exclude in title_lower:
                        return 0, f"❌ Role excluded: {title}", "excluded"
                
                return 15, f"⚠️ Related role: {title}", "related"
        
        # Check if any target role keyword appears
        for role in self.target_roles:
            # Check for partial matches (e.g., "analyst" in "Senior Business Analyst")
            role_words = role.split()
            if any(word in title_lower for word in role_words if len(word) > 3):
                return 20, f"🔶 Partial role match: {title}", "partial"
        
        return 0, f"❌ No role match: {title}", "none"
    
    def _match_skills(self, description: str, job_skills: List[str]) -> tuple:
        """
        Match job skills against user profile.
        
        Returns:
            (score, matched_skills, missing_skills)
        """
        if not description and not job_skills:
            return 10, [], []  # No info to match against
        
        # Combine description and job_skills for matching
        text_to_search = description.lower()
        if job_skills:
            text_to_search += ' ' + ' '.join(job_skills).lower()
        
        matched = []
        missing = []
        
        # Check each target skill
        for skill in self.target_skills:
            skill_lower = skill.lower()
            if skill_lower in text_to_search:
                matched.append(skill)
            else:
                # Check for partial matches (e.g., "SAP" matches "SAP S/4HANA")
                skill_short = skill_lower.split()[0] if ' ' in skill_lower else skill_lower
                if len(skill_short) > 2 and skill_short in text_to_search:
                    matched.append(skill)
        
        # Calculate score based on matches
        # 40 points for matching skills (scale with number of target skills)
        num_target = len(self.target_skills)
        if num_target > 0:
            # At least 1 match = base 10 points, +5 per additional match, max 40
            if len(matched) == 0:
                score = 5  # Some relevant but no direct matches
            else:
                score = min(10 + (len(matched) - 1) * 5, 40)
        else:
            score = 20  # No specific skills defined
        
        return score, matched, missing
    
    def _match_location(self, location: str) -> tuple:
        """
        Match job location against preferred locations.
        
        Returns:
            (score, reason)
        """
        if not location:
            return 10, "📍 Location: Not specified (default to interested)"
        
        loc_lower = location.lower()
        
        # Check for exact matches
        for pref_loc in self.target_locations:
            if pref_loc.lower() in loc_lower:
                return 15, f"📍 Location: {location} ✓"
        
        # Check for remote work
        remote_keywords = ['remote', 'work from home', 'wfh', 'anywhere', 'flexible']
        for keyword in remote_keywords:
            if keyword in loc_lower:
                return 15, f"📍 Location: Remote ✓"
        
        # Check for Jakarta area (Greater Jakarta)
        jakarta_keywords = ['jakarta', 'jabodetabek', 'tangerang', 'depok', 'bogor']
        for keyword in jakarta_keywords:
            if keyword in loc_lower:
                return 10, f"📍 Location: {location} (Greater Jakarta)"
        
        # Location not in preferences
        return 5, f"📍 Location: {location} (not preferred)"
    
    def _check_salary(self, salary_min: Optional[int], salary_max: Optional[int]) -> tuple:
        """
        Check if salary range is acceptable.
        
        Returns:
            (score, reason)
        """
        if not salary_min and not salary_max:
            return 10, "💰 Salary: Not specified"
        
        # If only max is provided
        if salary_max and not salary_min:
            if salary_max < self.salary_min:
                return 0, f"💰 Salary: {salary_max/1000000:.0f}M (below target)"
            elif salary_max > self.salary_max * 1.5:
                return 15, f"💰 Salary: Up to {salary_max/1000000:.0f}M (above target!)"
            else:
                return 15, f"💰 Salary: Up to {salary_max/1000000:.0f}M"
        
        # If only min is provided
        if salary_min and not salary_max:
            if salary_min < self.salary_min:
                return 5, f"💰 Salary: {salary_min/1000000:.0f}M+ (may be low)"
            else:
                return 15, f"💰 Salary: {salary_min/1000000:.0f}M+"
        
        # Both provided
        avg_salary = (salary_min + salary_max) / 2
        
        if salary_max < self.salary_min:
            return 0, f"💰 Salary: {salary_min/1000000:.0f}-{salary_max/1000000:.0f}M (below target)"
        elif salary_min > self.salary_max:
            return 15, f"💰 Salary: {salary_min/1000000:.0f}-{salary_max/1000000:.0f}M (above target!)"
        else:
            return 15, f"💰 Salary: {salary_min/1000000:.0f}-{salary_max/1000000:.0f}M ✓"
    
    def generate_explanation(self, match_result: MatchResult, job) -> str:
        """
        Generate a human-readable explanation for the match.
        
        Args:
            match_result: MatchResult from score_job()
            job: Job object
            
        Returns:
            String explanation
        """
        lines = [
            f"**{job.title}** at **{job.company}**",
            f"URL: {job.url}",
            "",
            f"Score: **{match_result.score}/100** - **{match_result.status.value}**",
            "",
            "**Match Details:**",
        ]
        
        for reason in match_result.reasons:
            lines.append(f"  • {reason}")
        
        if match_result.matched_skills:
            lines.append("")
            lines.append(f"**Matched Skills:** {', '.join(match_result.matched_skills)}")
        
        if match_result.missing_skills:
            lines.append("")
            lines.append(f"**You Have (not mentioned):** {', '.join(match_result.missing_skills[:5])}")
        
        return '\n'.join(lines)


def test_scorer():
    """Test the scorer with sample jobs"""
    from src.collectors.base import Job
    from datetime import datetime
    
    # Sample user profile
    profile = {
        'target_roles': ['ERP Analyst', 'Business Analyst', 'Operations Analyst'],
        'skills': ['SAP ECC', 'Odoo', 'SQL', 'Excel', 'Budgeting', 'Forecasting'],
        'locations': ['Jakarta', 'Bekasi', 'Remote'],
        'salary_min': 15000000,
        'salary_max': 25000000,
        'scoring': {'yes_threshold': 80, 'maybe_threshold': 50}
    }
    
    scorer = JobScorer(profile)
    
    # Sample jobs
    test_jobs = [
        Job(
            job_id="test1",
            title="ERP Business Analyst",
            company="Unilever",
            location="Jakarta",
            url="https://example.com/job1",
            source="Greenhouse",
            description="Looking for SAP ECC expert with experience in budgeting and forecasting."
        ),
        Job(
            job_id="test2",
            title="Marketing Manager",
            company="Shopee",
            location="Jakarta",
            url="https://example.com/job2",
            source="Lever",
            description="Lead marketing campaigns and team management."
        ),
        Job(
            job_id="test3",
            title="Business Operations Analyst",
            company="Grab",
            location="Remote",
            url="https://example.com/job3",
            source="Lever",
            description="Analyze business operations, improve processes, SQL knowledge required."
        ),
    ]
    
    print("=" * 60)
    print("JOB SCORING TEST")
    print("=" * 60)
    
    for job in test_jobs:
        result = scorer.score_job(job)
        print(f"\n{job.title} at {job.company}")
        print(f"  Score: {result.score}/100 - {result.status.value}")
        print(f"  Reasons: {result.reasons}")
        if result.matched_skills:
            print(f"  Matched Skills: {result.matched_skills}")


if __name__ == "__main__":
    test_scorer()