# Job Intelligence Platform

**AI-powered job opportunity discovery and tracking for Business Operations / ERP Analysts**

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Overview

This platform automatically discovers job opportunities from company career pages (via ATS platforms like Greenhouse, Lever, SmartRecruiters), evaluates them against your professional profile, and notifies you of high-quality matches.

**Key Feature**: Focuses on early discovery - finding opportunities on company career pages 3-7 days BEFORE they appear on job boards like JobStreet or Glints.

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [How It Works](#-how-it-works)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## ✨ Features

### Core Features
- **Company-First Discovery**: Monitor 20-30 target companies instead of scraping hundreds of job boards
- **ATS Integration**: Automatic collection from Greenhouse, Lever, and SmartRecruiters platforms
- **Smart Scoring**: Rule-based matching with YES/MAYBE/NO classification
- **Google Sheets Integration**: Track all opportunities in a familiar spreadsheet
- **Email Notifications**: Daily digest of new high-quality matches

### Supported ATS Platforms
| Platform | Companies | Status |
|----------|-----------|--------|
| Greenhouse | Unilever, Nestlé, SAP, GoTo | ✅ Working |
| Lever | Grab, Shopee | ✅ Working |
| SmartRecruiters | DHL | ✅ Working |
| Workday | Danone, Toyota, Astra | ⏳ Manual check |
| Other | Various | ⏳ Manual check |

## 🚀 Quick Start

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git (for cloning)
- Google account (for Sheets integration - optional)
- Gmail account (for email notifications - optional)

### 1. Clone the Repository

```bash
git clone https://github.com/fwidianto/AI-Job-Intelligence.git
cd AI-Job-Intelligence
```

### 2. Create Virtual Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
# Should display help without errors
python src/main.py --help

# Should run scorer tests without errors
python src/main.py --test-scorer
```

### 5. Configure Your Profile

Edit `config/user_profile.yaml`:

```yaml
target_roles:
  - ERP Analyst
  - Business Analyst
  - Operations Analyst

skills:
  - SAP ECC
  - Odoo ERP
  - SQL
  - Excel

locations:
  - Jakarta
  - Bekasi
  - Remote

salary_min: 15000000  # 15M IDR
salary_max: 25000000  # 25M IDR
```

### 6. Run the Platform

```bash
# Test mode (no external API calls)
python src/main.py --test-scorer

# Full run
python src/main.py

# Test collectors
python src/main.py --test-collectors
```

---

## 🐳 Docker Quick Start

### Build and Run

```bash
# Build image
docker build -t job-intelligence .

# Run with test
docker run --rm job-intelligence python src/main.py --test-scorer

# Interactive shell
docker run --rm -it job-intelligence /bin/bash
```

### Environment Variables

```bash
# Run with environment file
docker run --rm --env-file .env job-intelligence python src/main.py

# Or inline
docker run --rm \
  -e GOOGLE_SHEETS_ID=your-id \
  -e GOOGLE_CREDENTIALS=/app/credentials/service-account.json \
  job-intelligence python src/main.py
```

---

## 🔧 Configuration

### Environment Variables (Optional)

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_SHEETS_ID` | Your spreadsheet ID | No (uses mock) |
| `GOOGLE_CREDENTIALS` | Path to service account JSON | No (uses mock) |
| `EMAIL_SMTP_USER` | Gmail for notifications | No |
| `EMAIL_SMTP_PASSWORD` | Gmail App Password | No |
| `LOG_LEVEL` | Log level (INFO, DEBUG, etc.) | No |

### Profile Configuration

Edit `config/user_profile.yaml`:
- Target roles (job titles you're looking for)
- Your skills
- Preferred locations
- Salary range
- Email settings

### Companies Configuration

Edit `config/companies.yaml`:
- Add/remove target companies
- Set ATS platform for each company
- Adjust priorities

## 📝 Configuration

### User Profile (`config/user_profile.yaml`)

| Field | Description | Example |
|-------|-------------|---------|
| `target_roles` | Job titles you're looking for | `["ERP Analyst", "Business Analyst"]` |
| `skills` | Your skills for matching | `["SAP ECC", "SQL", "Excel"]` |
| `locations` | Preferred work locations | `["Jakarta", "Remote"]` |
| `salary_min` | Minimum acceptable salary (IDR) | `15000000` |
| `salary_max` | Maximum expected salary (IDR) | `25000000` |
| `email` | Email notification settings | See below |

### Companies (`config/companies.yaml`)

Add target companies with their ATS information:

```yaml
companies:
  - name: Unilever Indonesia
    industry: FMCG
    ats: greenhouse
    slug: unilever
    priority: 1
```

### Email Configuration

To enable email notifications:

1. Create a Gmail App Password:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Enable 2-Step Verification
   - Go to App Passwords
   - Create a new app password for "Job Intelligence"

2. Update `config/user_profile.yaml`:

```yaml
email:
  smtp_host: smtp.gmail.com
  smtp_port: 587
  smtp_user: your-email@gmail.com
  smtp_password: your-app-password
  from_addr: your-email@gmail.com
  to_addr:
    - your-email@gmail.com
  enabled: true
```

## 💻 Usage

### Command Line Options

```bash
# Full run with email notification
python src/main.py

# Test collectors only
python src/main.py --test-collectors

# Test scoring engine
python src/main.py --test-scorer

# Force email even with no new matches
python src/main.py --force-email

# Use custom config directory
python src/main.py --config /path/to/config
```

### Windows Scheduled Task (Daily Automation)

1. Open Task Scheduler
2. Create Basic Task
3. Name: `Job Intelligence Daily`
4. Trigger: Daily at 8:00 AM
5. Action: Start a program
   - Program: `python`
   - Arguments: `C:\job-intelligence\src\main.py`
   - Start in: `C:\job-intelligence`

### Google Sheets Setup

1. Create a new Google Sheet
2. Copy the spreadsheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit`
3. Set environment variable:
   ```bash
   export GOOGLE_SHEETS_ID="your-spreadsheet-id"
   ```
4. Run the platform - it will automatically create the sheet structure

## 📁 Project Structure

```
job-intelligence/
├── config/
│   ├── user_profile.yaml      # Your job search preferences
│   └── companies.yaml         # Target companies list
├── src/
│   ├── main.py                # Entry point
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py            # Base collector class
│   │   ├── greenhouse.py      # Greenhouse ATS collector
│   │   ├── lever.py           # Lever ATS collector
│   │   └── smartrecruiters.py # SmartRecruiters collector
│   ├── scorer.py              # Job scoring engine
│   ├── sheets.py              # Google Sheets integration
│   └── notifier.py            # Email notifications
├── credentials/               # Google API credentials (gitignored)
├── logs/                      # Log files (gitignored)
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── run.bat                    # Windows batch file to run
```

## 🔧 How It Works

### 1. Company Intelligence Layer

The platform maintains a list of 20-30 target companies with their:
- ATS platform (Greenhouse, Lever, etc.)
- Career page URL
- Priority score
- Last checked date

### 2. ATS Collectors

Each collector is specialized for one ATS platform:

```
Greenhouse Collector → company.greenhouse.io
Lever Collector → company.lever.co  
SmartRecruiters Collector → careers.company.com
```

### 3. Scoring Engine

Jobs are scored based on:

| Component | Max Points | Description |
|-----------|------------|-------------|
| Role Match | 30 | Title matches target roles |
| Skills Match | 40 | Your skills appear in job description |
| Location | 15 | Job location matches preferences |
| Salary | 15 | Salary range within target |

**Score Interpretation:**
- 80-100: ✅ YES - Apply immediately
- 50-79: ⚠️ MAYBE - Review and decide
- 0-49: ❌ NO - Skip

### 4. Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│  Companies  │────▶│  Collectors  │────▶│  Scorer   │
└─────────────┘     └──────────────┘     └─────┬─────┘
                                               │
                    ┌──────────────┐     ┌──────▼──────┐
                    │   Email      │◀────│  Sheets     │
                    └──────────────┘     └─────────────┘
```

## 🐛 Troubleshooting

### "Module not found" errors

Make sure you installed the dependencies:
```bash
pip install -r requirements.txt
```

### "No jobs found" or errors

1. Check if the company's ATS is accessible
2. Verify the company slug in `companies.yaml`
3. Check the logs in `logs/job_intelligence.log`

### Email not sending

1. Verify Gmail App Password is correct
2. Make sure 2-Step Verification is enabled on your Google account
3. Check that `enabled: true` is set in email config

### Google Sheets not working

1. Set the `GOOGLE_SHEETS_ID` environment variable
2. For full functionality, set up Google API credentials:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a project and enable Google Sheets API
   - Create OAuth credentials and save to `credentials/credentials.json`

## 📊 Portfolio Value

This project demonstrates:

1. **Data Engineering**
   - ETL pipelines (collect → normalize → store)
   - API integration with multiple platforms
   - Data deduplication

2. **Business Intelligence**
   - KPI tracking (application success rate)
   - Analytics dashboard (Google Sheets)
   - Data-driven decision making

3. **Automation**
   - Scheduled jobs (Windows Task Scheduler)
   - Email notifications
   - Error handling and recovery

4. **Domain Expertise**
   - ERP/Business Analyst skill mapping
   - Indonesian job market knowledge
   - Salary benchmarking

## 📄 License

MIT License - Feel free to use and modify for your own job search!

## 🙏 Acknowledgments

- Greenhouse, Lever, and SmartRecruiters for providing public APIs
- Google for Google Sheets and Gmail integration
- The Python community for excellent libraries

---

**Made for job seekers by a job seeker** 🚀