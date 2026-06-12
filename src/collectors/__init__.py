"""Job Intelligence Platform - ATS-Only Collectors Module

⚠️ STRICT RULE: This module ONLY contains ATS-specific collectors.
NO HTML scraping, GenericScraper, or job board scrapers.

Supported ATS:
- Greenhouse (API)
- Lever (API)
- SmartRecruiters (API)
- iCIMS (API)
- Workday (OData)
- SuccessFactors (OData)
"""

from .base import BaseCollector, Job, CollectorError
from .factory import CollectorFactory, register_collector

# ATS Collectors ONLY
from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .smartrecruiters import SmartRecruitersCollector
from .icims_collector import ICimsCollector, fetch_icims_jobs

# ATS Extractors (Workday, SuccessFactors)
from .ats_extractor import WorkdayExtractor, SuccessFactorsExtractor

# Source Validation
from .source_resolver import JobSourceResolver, ResolverResult

# Engine (optional orchestration)
from .engine import JobIntelligenceEngine, ProfileConfig, PipelineResult

__all__ = [
    # Base
    'BaseCollector',
    'Job',
    'CollectorError',
    
    # Factory (ATS-ONLY)
    'CollectorFactory',
    'register_collector',
    
    # ATS Collectors
    'GreenhouseCollector',
    'LeverCollector',
    'SmartRecruitersCollector',
    'ICimsCollector',
    'fetch_icims_jobs',
    
    # ATS Extractors
    'WorkdayExtractor',
    'SuccessFactorsExtractor',
    
    # Source Validation
    'JobSourceResolver',
    'ResolverResult',
    
    # Engine
    'JobIntelligenceEngine',
    'ProfileConfig',
    'PipelineResult',
]