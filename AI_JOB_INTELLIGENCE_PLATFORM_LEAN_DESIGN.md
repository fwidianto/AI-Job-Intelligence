# AI Job Intelligence Platform - Lean Architecture Design

**Version**: 2.0 (Job Seeker Perspective)
**Date**: 2026-06-11
**Author**: Senior Software Architect
**Objective**: Maximize interview opportunities while minimizing maintenance effort

---

## Executive Summary

This document presents a **lean architecture** for an AI-powered job intelligence platform designed for a Business Operations / ERP Analyst seeking roles in Indonesian multinational and large domestic companies.

**Core Insight**: The real value is **early discovery** - finding opportunities on company career pages 3-7 days before they appear on job boards.

**Design Philosophy**: 
- **Company-first** over job-board-first
- **Quality over quantity** - 20 great opportunities > 200 mediocre ones
- **Simplicity over comprehensiveness** - working MVP in 2 weeks
- **Maintenance-light** - minimal ongoing effort

---

## Part 1: Business Problem Analysis

### The Indonesian ERP/Business Analyst Market

**Target Roles:**
| Role | Demand Driver | Typical Employers |
|------|---------------|-------------------|
| ERP Analyst | SAP/Odoo implementations | Multinationals, large manufacturers |
| Business Analyst | Digital transformation | Tech companies, banks, telco |
| Operations Analyst | Process optimization | Manufacturing, logistics |
| Cost Control Analyst | Financial compliance | Large conglomerates |
| Finance Analyst | Reporting automation | All sectors |
| Reporting Analyst | BI adoption | Data-driven companies |

**Salary Range**: 15M–25M IDR monthly (approximately $9,600–$16,000 USD)

**Key Hiring Companies (Indonesian Market):**
1. **Multinational Corporations (MNCs)**: Unilever, Nestlé, Danone, Toyota, Honda, Astra, DHL, Maersk
2. **Tech Giants**: Grab, Shopee, GoTo, Tokopedia
3. **Large Indonesian Conglomerates**: Telkom, BRI, BCA, Semen Indonesia, Indofood
4. **Enterprise ERP Implementers**: SAP Indonesia partners, Odoo partners

**Critical Insight**: These companies often hire through:
- Direct career pages (70%)
- LinkedIn (20%)
- Headhunters/recruiters (10%)
- Job boards last (they get flooded with applications)

---

## Part 2: The Early Discovery Advantage

### Why Company Career Pages First

```
Day 0: Company posts job on their career page
Day 1-3: Early applicants apply directly (low competition)
Day 3-7: Job appears on JobStreet/Glints
Day 7-14: Job board applicants flood in (high competition)
Day 14+: Position likely filled or interview process started
```

**Implication**: Being first on career pages = 10x higher interview probability

### The Intelligence Gap

Most job seekers:
1. Wait for JobStreet/Glints notifications
2. Apply late when competition is high
3. Miss opportunities at companies they didn't know about

**Our Solution**: Build a Company Intelligence layer that monitors high-value targets and alerts when new opportunities appear.

---

## Part 3: Lean System Architecture

### Architecture Philosophy

**Smallest Possible Architecture:**
- Python scripts (no web framework)
- Google Sheets (as database and UI)
- Daily scheduled runs (Windows Task Scheduler)
- Email notifications (Gmail SMTP)

**What We're NOT Building:**
- No PostgreSQL/MySQL
- No React dashboard
- No complex microservices
- No real-time processing
- No mobile app

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   LEAN JOB INTELLIGENCE SYSTEM               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐                                    │
│  │  Company Intelligence │  ← Excel/Sheets - manual setup   │
│  │  (20-30 targets)     │                                    │
│  └──────────┬──────────┘                                    │
│              │                                              │
│              ▼                                              │
│  ┌─────────────────────┐                                    │
│  │  ATS Discovery      │  ← Identify company ATS platform   │
│  │  Engine              │                                    │
│  └──────────┬──────────┘                                    │
│              │                                              │
│              ▼                                              │
│  ┌─────────────────────┐                                    │
│  │  ATS Collectors     │  ← Greenhouse, Lever, SmartRecruiters│
│  │  (3 collectors)     │                                    │
│  └──────────┬──────────┘                                    │
│              │                                              │
│              ▼                                              │
│  ┌─────────────────────┐                                    │
│  │  Match Scorer       │  ← Simple keyword matching         │
│  │  (Rule-based)       │                                    │
│  └──────────┬──────────┘                                    │
│              │                                              │
│              ▼                                              │
│  ┌─────────────────────┐                                    │
│  │  Google Sheets      │  ← Data store + UI                 │
│  │  (5 sheets)         │                                    │
│  └──────────┬──────────┘                                    │
│              │                                              │
│              ▼                                              │
│  ┌─────────────────────┐                                    │
│  │  Email Alert        │  ← Gmail notification for new jobs │
│  │  (Daily digest)    │                                    │
│  └─────────────────────┘                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11 | Required by user |
| Scheduler | Windows Task Scheduler | Native, no extra install |
| Data Store | Google Sheets | Already using, easy to view/edit |
| HTTP Requests | requests library | Simple, well-documented |
| Email | Gmail SMTP | Free, reliable |
| Config | YAML files | Human-readable, easy to edit |

**No Additional Dependencies:**
- No APScheduler (Task Scheduler handles this)
- No Flask/Django (not needed for MVP)
- No SQL database (Sheets is sufficient)

---

## Part 4: Company Intelligence Layer

### Purpose

A curated list of 20-30 high-value target companies with their ATS information, career page URLs, and monitoring status.

### Company Intelligence Schema

**Sheet: Companies**

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| Company_Name | Text | Full company name | Unilever Indonesia |
| Industry | Text | Industry sector | FMCG/Consumer Goods |
| ATS_Platform | Text | Greenhouse/Lever/Workday/Other/Unknown | Greenhouse |
| Career_Page_URL | URL | Link to careers page | careers.unilever.com |
| ATS_Jobs_URL | URL | Direct link to their ATS jobs | unilever.greenhouse.io |
| Priority | Number | 1-5 (1=highest) | 1 |
| Last_Checked | Date | Last collection date | 2026-06-11 |
| Jobs_Found | Number | Total jobs found | 3 |
| Active_Jobs | Number | Currently active | 1 |
| Notes | Text | Manual notes | Preferred employer |

### Initial Target Companies (Indonesian Market)

#### Tier 1: MNCs with Known ATS (Start Here)
| Company | Industry | ATS | Jobs URL Pattern |
|---------|----------|-----|------------------|
| Unilever | FMCG | Greenhouse | unilever.greenhouse.io |
| Nestlé | FMCG | Greenhouse | nestle.greenhouse.io |
| Grab | Tech/T Transport | Lever | grab.jobs |
| Shopee | E-commerce | Lever | shopee.com/careers |
| DHL | Logistics | SmartRecruiters | dhl.com/careers |
| Danone | FMCG | Workday | danone.com/careers |
| Toyota | Automotive | Workday | toyota.co.id/careers |
| Astra | Conglomerate | Workday | astra.co.id/careers |

#### Tier 2: Large Indonesian Companies
| Company | Industry | ATS | Notes |
|---------|----------|-----|-------|
| Telkom | Telco | Unknown | Check manually |
| GoTo | Tech | Greenhouse | gojek.com/careers |
| BRI | Banking | Unknown | Often use headhunters |
| BCA | Banking | Unknown | Internal portal |
| Semen Indonesia | Manufacturing | Unknown | Check manually |
| Indofood | FMCG | Unknown | Multiple divisions |

#### Tier 3: ERP Implementers (High Value for ERP Analysts)
| Company | Industry | ATS | Notes |
|---------|----------|-----|-------|
| SAP Indonesia | IT/Consulting | Greenhouse | SAP partners |
| Odoo Indonesia | IT/Consulting | Unknown | Odoo partners |
| Accenture | Consulting | Workday | ERP projects |
| Deloitte | Consulting | Workday | SAP practice |
| PwC | Consulting | Workday | Finance consulting |

**Total Target: 20-25 companies for MVP**

---

## Part 5: ATS Discovery Engine

### Purpose

Automatically identify which ATS platform a company uses, enabling the correct collector to be used.

### Discovery Methods

#### Method 1: URL Pattern Detection (Primary)

Most companies use standard ATS platforms with predictable URL patterns:

| ATS Platform | URL Pattern | Example |
|--------------|-------------|---------|
| Greenhouse | {company}.greenhouse.io | unilever.greenhouse.io |
| Lever | {company}.lever.co | grab.lever.co |
| SmartRecruiters | careers.{company}.com | careers.dhl.com |
| Workday | {company}.workday.com | danone.workday.com |
| Taleo | taleo.{company}.com | taleo.oracle.com |

**Algorithm:**
```
1. Check if company has known ATS (from manual research)
2. If not, try common URL patterns
3. Send HTTP HEAD request to detect redirects
4. Check for ATS-specific headers or content
5. Fall back to manual discovery
```

#### Method 2: HTTP Response Analysis

```
GREENHOUSE indicators:
- X-Greenhouse-Token header
- greenhouse.io in source
- Specific JavaScript patterns

LEVER indicators:
- lever.co in source
- Static content with job listings
- Specific CSS classes

WORKDAY indicators:
- workday.com in source
- Complex JavaScript framework
- SSO patterns
```

#### Method 3: Meta Tag Detection

```html
<!-- Greenhouse -->
<meta name="greenhouse" content="verified">

<!-- Lever -->
<meta property="og:type" content="Lever">

<!-- SmartRecruiters -->
<meta name="smartrecruiters" content="verified">
```

### ATS Discovery Implementation

```python
def discover_ats(company_name, career_url):
    """Discover ATS platform for a company"""
    
    # Method 1: Check known patterns
    patterns = {
        'greenhouse': f'https://{slugify(company_name)}.greenhouse.io',
        'lever': f'https://{slugify(company_name)}.lever.co',
        'smartrecruiters': f'https://careers.{slugify(company_name)}.com',
        'workday': f'https://{slugify(company_name)}.workday.com',
    }
    
    for ats, url in patterns.items():
        if is_valid_url(url):
            return ats
    
    # Method 2: Check meta tags on career page
    content = fetch_page(career_url)
    ats = detect_ats_from_meta(content)
    if ats:
        return ats
    
    # Method 3: Manual fallback
    return 'unknown'
```

---

## Part 6: Data Collectors

### Collector Strategy

**Only 3 collectors needed for MVP:**
1. **Greenhouse Collector** - Covers Unilever, Nestlé, Grab, GoTo, SAP
2. **Lever Collector** - Covers Shopee, other Lever users
3. **SmartRecruiters Collector** - Covers DHL, Maersk

**Manual fallback for:**
- Workday companies (complex, enterprise SSO)
- Unknown ATS companies
- Direct career pages without ATS

### Collector Design

```python
# Base collector interface
class BaseCollector:
    def __init__(self, company, config):
        self.company = company
        self.config = config
    
    def fetch_jobs(self) -> List[Job]:
        """Fetch all jobs from company's ATS"""
        raise NotImplementedError
    
    def normalize_job(self, raw_job) -> Job:
        """Normalize raw job data to standard format"""
        raise NotImplementedError
```

### Greenhouse Collector

**API Endpoint**: `https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs`

**Response Structure:**
```json
{
  "jobs": [
    {
      "id": 12345,
      "title": "ERP Business Analyst",
      "location": {"name": "Jakarta, Indonesia"},
      "content": "Job description HTML",
      "absolute_url": "https://company.greenhouse.io/jobs/12345",
      "updated_at": "2026-06-10T10:00:00Z"
    }
  ]
}
```

**Implementation:**
```python
class GreenhouseCollector(BaseCollector):
    def fetch_jobs(self):
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.company.slug}/jobs"
        response = requests.get(url)
        return response.json()['jobs']
    
    def normalize_job(self, raw):
        return Job(
            job_id=f"gh_{raw['id']}",
            title=raw['title'],
            location=raw['location']['name'],
            url=raw['absolute_url'],
            company=self.company.name,
            source='Greenhouse',
            posted_date=parse_date(raw['updated_at'])
        )
```

### Lever Collector

**API Endpoint**: `https://api.lever.co/v0/postings/{company_slug}?mode=json`

**Response Structure:**
```json
{
  "posting": {
    "id": "abc123",
    "title": "Business Operations Analyst",
    "location": "Jakarta, Indonesia",
    "description": "Job description",
    "url": "https://company.lever.co/jobs/abc123",
    "postedAt": "2026-06-09T00:00:00Z"
  }
}
```

### SmartRecruiters Collector

**API Endpoint**: `https://www.smartrecruiters.com/api/public/postings?company={company_id}`

**Response Structure:**
```json
{
  "content": [
    {
      "id": "xyz789",
      "title": "Cost Control Analyst",
      "location": "Bekasi",
      "description": "Job description",
      "refNumber": "SR-REF-123"
    }
  ]
}
```

---

## Part 7: Simplified Scoring Engine

### Philosophy

**Keep it simple for MVP:**
- Binary match: Yes / No / Maybe
- Only 3 criteria: Role, Skills, Location
- No complex weighted scoring
- Human makes final decision

### Match Criteria

```python
def calculate_match(job, user_profile) -> MatchResult:
    """Simple rule-based matching"""
    
    # 1. Role Match (must have)
    role_match = match_role(job.title, user_profile.target_roles)
    if not role_match:
        return MatchResult(status='no', score=0, reasons=['Role not relevant'])
    
    # 2. Skills Match (should have at least 1)
    skills_match = match_skills(job.description, user_profile.skills)
    if skills_match.count < 1:
        return MatchResult(status='maybe', score=30, 
                          reasons=[f"Only {skills_match.count}/3+ skills matched"])
    
    # 3. Location Match (should prefer)
    location_match = match_location(job.location, user_profile.locations)
    if not location_match:
        return MatchResult(status='maybe', score=50, 
                          reasons=['Location not preferred'])
    
    # 4. Salary Check (warning only)
    if job.salary:
        if job.salary.max < user_profile.salary_min:
            return MatchResult(status='maybe', score=70, 
                              reasons=['Salary below target'])
    
    return MatchResult(status='yes', score=85, 
                      reasons=['Good role match with relevant skills'])
```

### Match Output

| Score | Status | Action |
|-------|--------|--------|
| 80-100 | ✅ YES | Apply immediately |
| 50-79 | ⚠️ MAYBE | Review and decide |
| 0-49 | ❌ NO | Skip |

### Match Reasons

Generate simple explanations:
- "Role: ERP Analyst ✓"
- "Skills: SAP, Odoo, SQL matched"
- "Location: Jakarta ✓"
- "Salary: 18M-22M within target"

---

## Part 8: Google Sheets Schema (Simplified)

### Sheet 1: Companies (Company Intelligence)

| Column | Type | Description |
|--------|------|-------------|
| A | Company_Name | Target company |
| B | Industry | Industry sector |
| C | ATS_Platform | greenhouse/lever/smartrecruiters/workday/other |
| D | Career_URL | Link to careers |
| E | Jobs_API_URL | ATS jobs endpoint |
| F | Priority | 1-5 |
| G | Last_Checked | Date |
| H | Total_Jobs_Found | Counter |
| I | Active_Jobs | Counter |
| J | Notes | Manual notes |

### Sheet 2: Jobs (Discovered Opportunities)

| Column | Type | Description |
|--------|------|-------------|
| A | ID | Unique ID (auto) |
| B | Date_Found | Discovery date |
| C | Company | Employer |
| D | Job_Title | Position |
| E | Location | Jakarta, Remote, etc. |
| F | URL | Job posting link |
| G | Source | ATS platform |
| H | Match_Status | YES/MAYBE/NO |
| I | Match_Reasons | Why it matched |
| J | Applied | YES/NO/PENDING |
| K | Applied_Date | Date |
| L | Interview | YES/NO |
| M | Outcome | Applied/Rejected/Interviewing/Hired |
| N | Notes | Personal notes |

### Sheet 3: Applied (Tracked Applications)

| Column | Type | Description |
|--------|------|-------------|
| A | Date_Applied | Application date |
| B | Company | Employer |
| C | Role | Position |
| D | Source | Where found |
| E | Status | Applied/Interview/Rejected |
| F | Last_Update | Date |
| G | Notes | Follow-up notes |

### Sheet 4: Analytics (Dashboard)

Using formulas for live metrics:

| Metric | Formula |
|--------|---------|
| Total Jobs Found | =COUNTA(Jobs!A:A)-1 |
| New This Week | =COUNTIF(Jobs!A:A, ">TODAY()-7") |
| Match Rate | =COUNTIF(Jobs!H:H,"YES")/COUNTA(Jobs!H:H) |
| Applications Sent | =COUNTIF(Applied!D:D,"Applied") |
| Interview Rate | =COUNTIF(Applied!E:E,"Interview")/COUNTIF(Applied!D:D,"Applied") |

---

## Part 9: 2-Week MVP Implementation Plan

### Week 1: Foundation (Days 1-5)

**Day 1-2: Setup & Company Intelligence**
- [ ] Create project directory
- [ ] Install Python dependencies
- [ ] Setup Google Sheets API credentials
- [ ] Build Company Intelligence sheet (20 target companies)
- [ ] Manually discover ATS for each company

**Day 3-4: First Collector (Greenhouse)**
- [ ] Build Greenhouse collector class
- [ ] Test with 3 companies (Unilever, Nestlé, SAP)
- [ ] Verify data flow to Google Sheets
- [ ] Handle errors gracefully

**Day 5: Basic Scoring + Email**
- [ ] Implement role matching
- [ ] Add location matching
- [ ] Setup Gmail SMTP
- [ ] Test email notification

**Week 1 Deliverable**: Manual company list + 1 working collector + email alerts

### Week 2: Working MVP (Days 6-10)

**Day 6-7: Additional Collectors**
- [ ] Build Lever collector
- [ ] Build SmartRecruiters collector
- [ ] Test with Shopee, DHL

**Day 8: Polish & Error Handling**
- [ ] Deduplication logic
- [ ] Error recovery
- [ ] Logging system
- [ ] Rate limiting (be respectful to servers)

**Day 9: Windows Scheduler**
- [ ] Setup daily scheduled run
- [ ] Test scheduled execution
- [ ] Verify email delivery

**Day 10: Documentation & Testing**
- [ ] Write README
- [ ] Test end-to-end flow
- [ ] Add 5 more companies
- [ ] Clean up code

**Week 2 Deliverable**: 3 collectors, daily automation, working MVP

### Post-MVP: Refinement (Week 3+)

Only if time permits:
- Add more companies (target 30)
- Implement AI scoring (OpenAI API)
- Build weekly reports
- Add CV generation

---

## Part 10: Risk Assessment & Mitigation

### Risk Matrix

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| ATS changes API | High | Medium | Log errors, manual fallback |
| Company blocks bot | Medium | Low | Respect rate limits, use proper headers |
| Gmail SMTP issues | Medium | Low | Test monthly, backup notification method |
| Google Sheets quota | Low | Very Low | Stay well under limits |
| Job posting removed | Low | Medium | Re-check before applying |

### Maintenance Effort

**Daily (Automated):**
- 5 minutes: Check email alerts, review new matches
- 0 minutes: System runs automatically

**Weekly:**
- 15 minutes: Review analytics, adjust scoring
- 10 minutes: Check for failed runs

**Monthly:**
- 30 minutes: Add new companies, update priorities

**Total Maintenance**: ~1 hour per month (very low)

---

## Part 11: Portfolio Value Additions

### For Business Operations / ERP Analyst Portfolio

This project demonstrates:

1. **Data Engineering**
   - ETL pipelines (collect → normalize → store)
   - Data deduplication
   - API integration

2. **Business Intelligence**
   - KPI tracking (application success rate)
   - Analytics dashboard
   - Data-driven decision making

3. **Automation**
   - Scheduled jobs (Windows Task Scheduler)
   - Email notifications
   - Error handling and recovery

4. **Domain Expertise**
   - ERP/Business Analyst skill mapping
   - Indonesian job market knowledge
   - Salary benchmarking

### Suggested Additions for Portfolio Impact

1. **Skills Gap Analysis**
   - Compare your skills against job requirements
   - Identify training needs

2. **Salary Intelligence**
   - Track salary ranges by company
   - Negotiation insights

3. **Application Pipeline**
   - Visual funnel: Found → Applied → Interview → Hired
   - Time-to-response tracking

4. **Weekly Executive Report**
   - PDF summary for yourself or mentor
   - Market trends from collected data

---

## Part 12: Code Structure (MVP)

```
job-intelligence/
├── config/
│   ├── user_profile.yaml      # Target roles, skills, locations
│   └── companies.yaml         # Company list with ATS info
├── src/
│   ├── main.py                # Entry point
│   ├── collectors/
│   │   ├── base.py            # Abstract collector
│   │   ├── greenhouse.py      # Greenhouse collector
│   │   ├── lever.py           # Lever collector
│   │   └── smartrecruiters.py # SmartRecruiters collector
│   ├── scorer.py              # Simple matching
│   ├── sheets.py              # Google Sheets API
│   └── notifier.py            # Email notifications
├── credentials/
│   └── .gitkeep
├── requirements.txt
├── README.md
└── run.bat                    # Windows batch file
```

**Total Python files: ~8**
**Total lines of code estimate: ~800-1000**

---

## Part 13: Configuration Files

### user_profile.yaml

```yaml
target_roles:
  - ERP Analyst
  - Business Analyst
  - Operations Analyst
  - Cost Control Analyst
  - Finance Analyst
  - Reporting Analyst
  - Data Analyst

skills:
  - SAP ECC
  - Odoo ERP
  - SQL
  - Google Sheets
  - Looker Studio
  - Business Intelligence
  - Budgeting
  - Forecasting

locations:
  - Jakarta
  - Bekasi
  - Karawang
  - Remote

salary_min: 15000000  # 15M IDR
salary_max: 25000000  # 25M IDR

email:
  smtp_host: smtp.gmail.com
  smtp_port: 587
  from_addr: your-email@gmail.com
  to_addr: your-email@gmail.com
```

### companies.yaml

```yaml
companies:
  - name: Unilever Indonesia
    industry: FMCG
    ats: greenhouse
    slug: unilever
    priority: 1
    notes: "Top employer, often has ERP roles"
    
  - name: Nestlé Indonesia
    industry: FMCG
    ats: greenhouse
    slug: nestle
    priority: 1
    notes: "SAP environment"
    
  - name: Grab Indonesia
    industry: Tech/Travel
    ats: lever
    slug: grab
    priority: 1
    notes: "Operations roles in demand"
    
  # ... add 20-25 companies
```

---

## Conclusion: Why This Works

### Traditional Approach vs. Lean Approach

| Aspect | Traditional | Lean (This Design) |
|--------|-------------|-------------------|
| Focus | All job boards | Target companies |
| Data Volume | 1000s of jobs | 20-30 companies |
| Quality | Low signal-to-noise | High signal |
| Maintenance | High | Low |
| Time to MVP | 3+ months | 2 weeks |
| Interview Rate | Low | Higher (early discovery) |

### Success Metrics

- **20-30 companies monitored** (not 100s of job boards)
- **Daily check automation** (set and forget)
- **New opportunities within 24 hours** of posting
- **< 1 hour/month maintenance** effort
- **5-10 quality applications/month** (not 50 mediocre ones)

### Key Insight

> "It's better to apply to 5 perfect jobs and get 2 interviews than to apply to 100 jobs and get none."

This lean architecture maximizes interview opportunities by:
1. Finding jobs BEFORE they appear on job boards
2. Focusing on companies that actually hire ERP/Business Analysts
3. Automating discovery so you can focus on preparation
4. Reducing noise so you can focus on quality

---

## Next Steps

1. **Review this design** - Does it align with your job search priorities?
2. **Approve the approach** - Company-first, ATS collectors, Google Sheets
3. **Approve the timeline** - 2-week MVP is realistic
4. **Confirm target companies** - Add your preferred employers to the list
5. **Begin implementation** - Start with Company Intelligence setup

---

**Document Version**: 2.0
**Status**: Ready for Review
**Next Action**: Proceed to implementation upon approval