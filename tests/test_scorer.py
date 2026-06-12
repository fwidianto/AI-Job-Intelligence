"""
Tests for Job Scoring Engine
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.collectors.base import Job
from src.scorer import JobScorer, MatchStatus


class TestJobScorer:
    """Test cases for JobScorer"""
    
    @classmethod
    def setup_class(cls):
        """Setup test fixtures"""
        cls.profile = {
            'target_roles': ['ERP Analyst', 'Business Analyst', 'Operations Analyst'],
            'skills': ['SAP ECC', 'Odoo', 'SQL', 'Excel', 'Budgeting', 'Forecasting'],
            'locations': ['Jakarta', 'Bekasi', 'Remote'],
            'salary_min': 15000000,
            'salary_max': 25000000,
            'scoring': {'yes_threshold': 80, 'maybe_threshold': 50}
        }
        cls.scorer = JobScorer(cls.profile)
    
    def test_exact_role_match(self):
        """Test exact role match scoring"""
        job = Job(
            job_id="test1",
            title="ERP Business Analyst",
            company="Unilever",
            location="Jakarta",
            url="https://example.com/job",
            source="Test",
            description="SAP ECC experience required. SQL and Excel skills needed."
        )
        
        result = self.scorer.score_job(job)
        
        assert result.status == MatchStatus.YES
        assert result.score >= 80
        assert "ERP" in result.role_match or "analyst" in result.role_match.lower()
    
    def test_related_role_match(self):
        """Test related role match scoring"""
        job = Job(
            job_id="test2",
            title="Operations Specialist",
            company="Grab",
            location="Remote",
            url="https://example.com/job",
            source="Test",
            description="Process optimization experience. Excel required."
        )
        
        result = self.scorer.score_job(job)
        
        assert result.status in [MatchStatus.YES, MatchStatus.MAYBE]
        assert result.score >= 50
    
    def test_no_role_match(self):
        """Test job with no relevant role"""
        job = Job(
            job_id="test3",
            title="Marketing Manager",
            company="Shopee",
            location="Jakarta",
            url="https://example.com/job",
            source="Test",
            description="Lead marketing campaigns."
        )
        
        result = self.scorer.score_job(job)
        
        assert result.status == MatchStatus.NO
        assert result.score < 50
    
    def test_skills_matching(self):
        """Test skills matching"""
        job = Job(
            job_id="test4",
            title="Business Analyst",
            company="DHL",
            location="Jakarta",
            url="https://example.com/job",
            source="Test",
            description="SAP and SQL experience required. Budgeting experience preferred."
        )
        
        result = self.scorer.score_job(job)
        
        assert len(result.matched_skills) > 0
        assert 'SAP' in result.matched_skills or 'SQL' in result.matched_skills
    
    def test_location_matching(self):
        """Test location matching"""
        job = Job(
            job_id="test5",
            title="ERP Analyst",
            company="Nestle",
            location="Jakarta",
            url="https://example.com/job",
            source="Test",
            description="SAP experience required."
        )
        
        result = self.scorer.score_job(job)
        
        assert result.location_match == True
    
    def test_remote_location(self):
        """Test remote work location"""
        job = Job(
            job_id="test6",
            title="Data Analyst",
            company="GoTo",
            location="Work from Home",
            url="https://example.com/job",
            source="Test",
            description="SQL and Excel required."
        )
        
        result = self.scorer.score_job(job)
        
        assert result.location_match == True
    
    def test_excluded_role(self):
        """Test that excluded roles get low scores"""
        job = Job(
            job_id="test7",
            title="Senior Software Engineer",
            company="Grab",
            location="Jakarta",
            url="https://example.com/job",
            source="Test",
            description="Java and Python development."
        )
        
        result = self.scorer.score_job(job)
        
        assert result.status == MatchStatus.NO
    
    def test_salary_check(self):
        """Test salary range matching"""
        job = Job(
            job_id="test8",
            title="Finance Analyst",
            company="Toyota",
            location="Jakarta",
            url="https://example.com/job",
            source="Test",
            description="Financial analysis experience.",
            salary_min=18000000,
            salary_max=22000000
        )
        
        result = self.scorer.score_job(job)
        
        assert result.score > 0


def run_tests():
    """Run all tests"""
    print("=" * 60)
    print("Running Job Scorer Tests")
    print("=" * 60)
    
    tester = TestJobScorer()
    tester.setup_class()
    
    tests = [
        ('Exact Role Match', tester.test_exact_role_match),
        ('Related Role Match', tester.test_related_role_match),
        ('No Role Match', tester.test_no_role_match),
        ('Skills Matching', tester.test_skills_matching),
        ('Location Matching', tester.test_location_matching),
        ('Remote Location', tester.test_remote_location),
        ('Excluded Role', tester.test_excluded_role),
        ('Salary Check', tester.test_salary_check),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {name}: Unexpected error - {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)