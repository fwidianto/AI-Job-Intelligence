"""
Tests for Job Collectors
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.collectors.base import Job, BaseCollector, CollectorError
from src.collectors.greenhouse import GreenhouseCollector
from src.collectors.lever import LeverCollector
from src.collectors.smartrecruiters import SmartRecruitersCollector


class TestGreenhouseCollector:
    """Test cases for Greenhouse collector"""
    
    def test_normalize_job(self):
        """Test job normalization"""
        collector = GreenhouseCollector("Test Company", "test", {})
        
        raw_job = {
            'id': 12345,
            'title': 'Business Analyst',
            'location': {'name': 'Jakarta, Indonesia'},
            'absolute_url': 'https://test.greenhouse.io/jobs/12345',
            'content': '<p>SAP and SQL required</p>',
            'updated_at': '2026-06-10T10:00:00Z'
        }
        
        job = collector.normalize_job(raw_job)
        
        assert job.job_id == 'gh_12345'
        assert job.title == 'Business Analyst'
        assert 'Jakarta' in job.location
        assert job.source == 'Greenhouse'
        assert 'SAP' in job.skills or 'SQL' in job.skills


class TestLeverCollector:
    """Test cases for Lever collector"""
    
    def test_normalize_job(self):
        """Test job normalization"""
        collector = LeverCollector("Test Company", "test", {})
        
        raw_job = {
            'id': 'abc123',
            'title': 'Operations Analyst',
            'location': 'Jakarta',
            'description': 'Process improvement experience required',
            'absolute_url': 'https://test.lever.co/jobs/abc123',
            'postedAt': '2026-06-10T00:00:00Z'
        }
        
        job = collector.normalize_job(raw_job)
        
        assert job.job_id == 'lev_abc123'
        assert job.title == 'Operations Analyst'
        assert job.location == 'Jakarta'


class TestSmartRecruitersCollector:
    """Test cases for SmartRecruiters collector"""
    
    def test_normalize_job(self):
        """Test job normalization"""
        collector = SmartRecruitersCollector("DHL", "dhl", {})
        
        raw_job = {
            'id': 'xyz789',
            'refNumber': 'DHL-123',
            'title': 'Finance Controller',
            'location': {'city': 'Jakarta', 'country': 'Indonesia'},
            'description': 'SAP experience preferred',
            'publishedOn': '2026-06-10T00:00:00Z'
        }
        
        job = collector.normalize_job(raw_job)
        
        assert job.job_id == 'sr_xyz789'
        assert job.title == 'Finance Controller'
        assert 'Jakarta' in job.location


def run_tests():
    """Run all tests"""
    print("=" * 60)
    print("Running Collector Tests")
    print("=" * 60)
    
    testers = [
        ('Greenhouse Normalize', TestGreenhouseCollector()),
        ('Lever Normalize', TestLeverCollector()),
        ('SmartRecruiters Normalize', TestSmartRecruitersCollector()),
    ]
    
    passed = 0
    failed = 0
    
    for name, tester in testers:
        try:
            if 'greenhouse' in name.lower():
                tester.test_normalize_job()
            elif 'lever' in name.lower():
                tester.test_normalize_job()
            elif 'smartrecruiters' in name.lower():
                tester.test_normalize_job()
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