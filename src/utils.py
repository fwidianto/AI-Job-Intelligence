"""
Utility functions for cross-platform compatibility.

This module provides safe text output for logging, ensuring
compatibility with Windows cp1252 terminals and other
restricted character encodings.
"""

import os
import sys
import logging
from typing import Optional


# =============================================================================
# EMOJI TO TEXT MAPPING
# =============================================================================

# Safe text equivalents for emojis (cross-platform)
EMOJI_MAP = {
    '📊': '[INFO]',
    '✅': '[OK]',
    '❌': '[ERROR]',
    '⚠️': '[WARN]',
    '⏭️': '[SKIP]',
    '⏱️': '[TIME]',
    '🔍': '[SEARCH]',
    '📧': '[EMAIL]',
    '📋': '[LIST]',
    '📝': '[NOTE]',
    '⭐': '[STAR]',
    '🔥': '[HOT]',
    '💼': '[JOB]',
    '🏢': '[COMPANY]',
    '📍': '[LOCATION]',
    '💰': '[SALARY]',
    '🔗': '[URL]',
    '⏰': '[CLOCK]',
    '🔄': '[REFRESH]',
    '⚡': '[FAST]',
}


def safe_text(text: str) -> str:
    """
    Convert text with emojis to safe cross-platform text.
    
    Args:
        text: Text potentially containing emojis
        
    Returns:
        Text with emojis replaced by safe alternatives
    """
    if not text:
        return ""
    
    result = text
    for emoji, replacement in EMOJI_MAP.items():
        result = result.replace(emoji, replacement)
    
    return result


def safe_log(text: str) -> str:
    """
    Prepare text for logging (remove emojis).
    
    Args:
        text: Text to prepare for logging
        
    Returns:
        Emoji-free text safe for all terminals
    """
    return safe_text(text)


# =============================================================================
# SAFE LOGGING CONFIGURATION
# =============================================================================

def setup_safe_logging(
    name: str = __name__,
    level: int = logging.INFO,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging with cross-platform emoji support.
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create formatter that removes emojis
    class SafeFormatter(logging.Formatter):
        def format(self, record):
            msg = super().format(record)
            return safe_text(msg)
    
    formatter = SafeFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


class SafeLogger:
    """
    Wrapper around logging that automatically sanitizes emoji characters.
    
    Usage:
        logger = SafeLogger(__name__)
        logger.info("Processing company: Grab")
        logger.warning("Skipping: Nestlé (custom site)")
        logger.error("Failed to fetch: SAP")
    """
    
    def __init__(self, name: str = __name__):
        self._logger = logging.getLogger(name)
    
    def _sanitize(self, *args, **kwargs) -> tuple:
        """Convert any emoji-containing args to safe text"""
        sanitized_args = tuple(safe_text(str(a)) for a in args)
        sanitized_kwargs = {k: safe_text(str(v)) for k, v in kwargs.items()}
        return sanitized_args, sanitized_kwargs
    
    def debug(self, msg: str, *args, **kwargs):
        args, kwargs = self._sanitize(*args, **kwargs)
        self._logger.debug(safe_text(msg), *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        args, kwargs = self._sanitize(*args, **kwargs)
        self._logger.info(safe_text(msg), *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        args, kwargs = self._sanitize(*args, **kwargs)
        self._logger.warning(safe_text(msg), *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        args, kwargs = self._sanitize(*args, **kwargs)
        self._logger.error(safe_text(msg), *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        args, kwargs = self._sanitize(*args, **kwargs)
        self._logger.critical(safe_text(msg), *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        args, kwargs = self._sanitize(*args, **kwargs)
        self._logger.exception(safe_text(msg), *args, **kwargs)


# =============================================================================
# ASCII LOGO (Cross-Platform)
# =============================================================================

LOGO = r"""
 ____             __        __         _    __  ____              
|  _ \  __ _  __ _\ \      / /__  _ __| | _ / _|/ ___|_____      __
| | | |/ _` |/ _` |\ \ /\ / / _ \| '__| |/ / |_ / __|_  / \  / /
| |_| | (_| | (_| | \ V  V / (_) | |  |   <|  _| \__ \/ / \ \/ / 
|____/ \__,_|\__, |  \_/\_/ \___/|_|  |_|\_\_|_||_|___/_____/_/\_\ 
             |___/                                                   
"""


def print_banner():
    """Print cross-platform banner"""
    print(LOGO)
    print("Job Intelligence Platform - Cross-Platform Edition")
    print("=" * 60)


# =============================================================================
# COMPANY VALIDATION UTILITIES
# =============================================================================

# Known working ATS configurations (verified)
VERIFIED_ATS = {
    'greenhouse': [
        'unilever',
        'stripe',
        'airbnb',
        'shopify',
    ],
    'lever': [
        'coinbase',
        'figma',
        'notion',
    ],
    'smartrecruiters': [
        'dhl',
    ],
}

# Known broken configurations (verified)
BROKEN_CONFIGS = {
    'nestle': {
        'expected': 'greenhouse',
        'actual': 'other',
        'career_url': 'https://www.nestle.com/careers',
        'fix': 'Use manual URL discovery or direct scraping',
    },
    'grab': {
        'expected': 'lever',
        'actual': 'other',
        'career_url': 'https://grab.com/careers/',
        'fix': 'Use direct career page URL',
    },
    'goto': {
        'expected': 'greenhouse',
        'actual': 'other',
        'career_url': 'https://www.gotocompany.com/careers',
        'fix': 'Use direct career page URL',
    },
    'sap': {
        'expected': 'greenhouse',
        'actual': 'other',
        'career_url': 'https://www.sap.com/indonesia/careers',
        'fix': 'Use SAP Careers page directly',
    },
}


def validate_company_config(company: dict) -> dict:
    """
    Validate a company configuration.
    
    Args:
        company: Company config dict from companies.yaml
        
    Returns:
        Validation result dict with status and recommendations
    """
    name = company.get('name', 'Unknown')
    ats = company.get('ats', 'other')
    slug = company.get('slug', '')
    career_url = company.get('career_url', '')
    
    result = {
        'name': name,
        'ats': ats,
        'slug': slug,
        'career_url': career_url,
        'status': 'unknown',
        'issues': [],
        'recommendations': [],
    }
    
    # Check slug format
    if not slug:
        result['issues'].append('Missing slug')
        result['recommendations'].append('Add slug for ATS URL construction')
    
    # Check career URL
    if not career_url:
        result['issues'].append('Missing career_url')
        result['recommendations'].append('Add career URL for manual check')
    
    # Check for known broken configs
    slug_lower = slug.lower()
    if slug_lower in BROKEN_CONFIGS:
        broken = BROKEN_CONFIGS[slug_lower]
        result['status'] = 'broken'
        result['issues'].append(f"Expected ATS '{broken['expected']}' is incorrect")
        result['recommendations'].append(broken['fix'])
    
    # Check if ATS is supported
    supported_ats = ['greenhouse', 'lever', 'smartrecruiters']
    if ats not in supported_ats:
        result['status'] = 'manual'
        result['issues'].append(f"ATS '{ats}' not supported for auto-collection")
        result['recommendations'].append('Mark as manual check or use URL discovery')
    
    # Set default status
    if result['status'] == 'unknown':
        if slug and slug_lower in VERIFIED_ATS.get(ats, []):
            result['status'] = 'working'
        else:
            result['status'] = 'unverified'
    
    return result


if __name__ == "__main__":
    # Test safe logging
    logger = SafeLogger("test")
    print("\n" + "=" * 60)
    print("Testing Safe Logger")
    print("=" * 60)
    
    logger.info("Processing: 📊 Unilever (Greenhouse)")
    logger.warning("Skipping: ⏭️ Nestlé (Custom site)")
    logger.error("Error: ❌ Failed to fetch jobs")
    
    print("\nWith safe_text():")
    print(safe_text("📊 Processing: Grab ⏭️ Skipping"))
    
    print("\n" + "=" * 60)
    print("Testing Company Validation")
    print("=" * 60)
    
    test_companies = [
        {'name': 'Grab', 'ats': 'lever', 'slug': 'grab', 'career_url': 'https://grab.com/careers/'},
        {'name': 'Unilever', 'ats': 'greenhouse', 'slug': 'unilever', 'career_url': 'https://www.unilever.com/careers/'},
        {'name': 'Nestlé', 'ats': 'greenhouse', 'slug': 'nestle', 'career_url': 'https://www.nestle.com/careers'},
    ]
    
    for company in test_companies:
        result = validate_company_config(company)
        print(f"\n{result['name']}:")
        print(f"  ATS: {result['ats']}, Status: {result['status']}")
        if result['issues']:
            print(f"  Issues: {', '.join(result['issues'])}")
        if result['recommendations']:
            print(f"  Fix: {result['recommendations'][0]}")