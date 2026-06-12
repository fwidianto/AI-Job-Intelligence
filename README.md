# AI Job Intelligence Platform v2

**ATS-First Job Discovery System for Business Operations / ERP Analysts**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Tests](https://img.shields.io/badge/Tests-11%2F11%20PASSING-brightgreen.svg)

## Overview

This platform is a **Job Data Intelligence Engine**, not a web scraper. It discovers job opportunities from structured ATS APIs, validates sources, and delivers high-quality matches directly to your Google Sheets.

**Key Principle**: "We do not scrape companies. We resolve jobs."

### Architecture Highlights (v2)

| Priority | Method | Description |
|----------|--------|-------------|
| 1st | **ATS-FIRST** | Greenhouse, Lever, SmartRecruiters, iCIMS APIs |
| 2nd | **NETWORK INTERCEPT** | Playwright-based API discovery |
| 3rd | **SOURCE VALIDATION** | Validates job endpoints before use |
| 4th | **HTML Parsing** | Workday, SuccessFactors (last resort) |
| 5th | **Dynamic Scraping** | Playwright for JavaScript pages (last resort) |

## Features

### Core Features
- **API-First Architecture**: Uses ATS public APIs (>70% job data from structured endpoints)
- **ATS Collectors**: Greenhouse, Lever, SmartRecruiters, iCIMS, Workday, SuccessFactors
- **Network Interception**: Captures XHR/Fetch calls to discover hidden APIs
- **Source Validation**: Validates every source before accepting job data
- **Smart Scoring**: YES/MAYBE/NO classification with confidence scores
- **Google Sheets Integration**: Track all opportunities in spreadsheet
- **Email Notifications**: Daily digest of matched opportunities

### Supported ATS Platforms

| Platform | Type | Companies | Status |
|----------|------|-----------|--------|
| Greenhouse | API | Unilever, Nestle, GoTo | Working |
| Lever | API | Grab, Shopee | Working |
| SmartRecruiters | API | DHL, Maersk | Working |
| iCIMS | API | Fortune 500 | Working |
| Workday | OData | Danone, Toyota | Working |
| SuccessFactors | OData | Astra, Shopee | Working |

### Data Quality Standards

Every job entry includes:
- `apply_url` (REQUIRED - must be valid endpoint)
- `source_confidence` (0.0-1.0: API=0.95, HTML=0.5)
- `extraction_method` ('api', 'network_intercept', 'html', 'scraped')
- `validated_source` flag

## Quick Start

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git
- Google account (optional)
- Gmail account (optional)

### 1. Clone and Setup

```bash
git clone https://github.com/fwidianto/AI-Job-Intelligence.git
cd AI-Job-Intelligence
python -m venv venv
source venv/bin/activate  # Linux/macOS
# OR: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
python src/main.py --test-scorer
python src/main.py --test-collectors
```

### 3. Configure Profile

Edit `config/user_profile.yaml`:

```yaml
target_roles:
  - ERP Analyst
  - Business Analyst
  - Operations Analyst
  - Data Analyst

skills:
  - SAP ECC
  - SAP S/4HANA
  - Odoo ERP
  - SQL
  - Excel
  - Power BI

locations:
  - Jakarta
  - Bekasi
  - Remote

salary_min: 15000000  # 15M IDR
salary_max: 25000000  # 25M IDR
```

### 4. Run the Platform

```bash
# Full run
python src/main.py

# Daily mode
python src/main.py --daily

# Dry run (no Google Sheets writes)
python src/main.py --dry-run
```

## Project Structure

```
job-intelligence/
├── config/
│   ├── user_profile.yaml     # Your job search preferences
│   └── companies.yaml        # Target companies with ATS info
├── src/
│   ├── main.py               # Entry point
│   ├── collectors/           # ATS collectors & discovery
│   │   ├── base.py           # Job data model (v2 with apply_url)
│   │   ├── factory.py         # Collector factory
│   │   ├── greenhouse.py      # Greenhouse API
│   │   ├── lever.py           # Lever API
│   │   ├── smartrecruiters.py # SmartRecruiters API
│   │   ├── icims_collector.py # iCIMS API
│   │   ├── ats_extractor.py   # Workday/SuccessFactors
│   │   ├── network_intercept.py # Playwright API capture
│   │   ├── company_discovery.py # Source validation
│   │   ├── source_resolver.py # Job source resolver
│   │   ├── search_discovery.py # Search-based discovery
│   │   └── engine.py          # Main orchestrator
│   ├── scorer.py              # Job scoring engine
│   ├── detectors/             # ATS detection
│   ├── sheets.py              # Google Sheets integration
│   └── notifier.py            # Email notifications
├── tests/
│   ├── test_scorer.py        # 8 tests
│   └── test_collectors.py     # 3 tests
└── requirements.txt
```

## Configuration

### Environment Variables

```bash
export GOOGLE_SHEETS_ID="your-spreadsheet-id"
export GOOGLE_CREDENTIALS="/path/to/credentials.json"
export EMAIL_SMTP_USER="your-email@gmail.com"
export EMAIL_SMTP_PASSWORD="your-app-password"
```

### Company Configuration

Add companies to `config/companies.yaml`:

```yaml
companies:
  - name: Grab
    industry: Technology
    ats: lever
    slug: grab
    priority: 1
  - name: Shopee Indonesia
    industry: E-commerce
    ats: successfactors
    slug: shopee
    priority: 1
  - name: Unilever Indonesia
    industry: FMCG
    ats: greenhouse
    slug: unilever
    priority: 1
```

## How It Works

### 1. Source Discovery

```
Company URL → CompanyURLDiscovery → Validated Source
                                     ↓
                              ATS Detected?
                              ↓         ↓
                          Yes         No
                              ↓         ↓
                     Use ATS API   Use Network Intercept
```

### 2. Job Ingestion Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    JOB INGESTION PIPELINE                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Priority 1: API-FIRST                                      │
│  └── Greenhouse → Lever → SmartRecruiters → iCIMS         │
│                                                             │
│  Priority 2: NETWORK INTERCEPT (Playwright)               │
│  └── Capture XHR/Fetch/GraphQL calls                       │
│                                                             │
│  Priority 3: SOURCE VALIDATION                             │
│  └── DiscoveredSource → is_valid → confidence_score        │
│                                                             │
│  Priority 4: HTML (last resort)                            │
│  └── Workday → SuccessFactors                               │
│                                                             │
│  Priority 5: SCRAPED (last resort)                         │
│  └── DynamicScraper with Playwright                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3. Scoring Engine

| Component | Max Points | Description |
|-----------|------------|-------------|
| Role Match | 30 | Title matches target roles |
| Skills Match | 40 | Your skills appear in description |
| Location | 15 | Job location matches preferences |
| Salary | 15 | Salary range within target |

**Score Thresholds:**
- 70-100: **YES** - Apply immediately
- 50-69: **MAYBE** - Review and decide
- 0-49: **NO** - Skip

## Architecture Compliance

| Requirement | Status |
|-------------|--------|
| ATS-First extraction | Implemented |
| Network intercept mode | Implemented |
| Source validation layer | Implemented |
| Company URL resolution | Implemented |
| Data quality enforcement | Implemented |
| Fallback order (API→Network→HTML→Scraped) | Implemented |
| Valid apply_url required | Enforced |

## Testing

```bash
# Run all tests
python tests/test_scorer.py    # 8 tests
python tests/test_collectors.py # 3 tests

# CLI tests
python src/main.py --test-scorer
python src/main.py --test-collectors
```

**Test Results: 11/11 PASSING**

## Docker

```bash
# Build
docker build -t job-intelligence .

# Run
docker run --rm job-intelligence python src/main.py --test-scorer
```

## Portfolio Value

This project demonstrates:

1. **Data Engineering**
   - ETL pipelines (collect → normalize → store)
   - Multi-source API integration
   - Data deduplication and validation

2. **Business Intelligence**
   - KPI tracking (match rates)
   - Analytics dashboard (Google Sheets)
   - Data-driven job search

3. **Automation & AI**
   - Scheduled job discovery
   - Intelligent matching engine
   - Email notifications

4. **ATS Architecture**
   - API-first design pattern
   - Network interception capabilities
   - Source validation systems

## License

MIT License - Feel free to use and modify for your own job search!

## Acknowledgments

- **Greenhouse**, **Lever**, **SmartRecruiters** for public APIs
- **SAP SuccessFactors**, **Workday** for enterprise ATS
- **Google** for Sheets and Gmail integration
- **Playwright** for browser automation

---

**System Status**: Production Ready  
**Test Coverage**: 11/11 Passing  
**Architecture**: API-First, ATS-Driven  

**Built for job seekers by a job seeker**