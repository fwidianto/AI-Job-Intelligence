from src.sheets import SheetConfig, SheetsManager

config = SheetConfig(
    spreadsheet_id="1uSyojRk_-ASHlKY_T08XOdOaXGmFSO9EM4viGRDF_70",
    credentials_file="credentials/credentials.json"
)

manager = SheetsManager(config)

job = {
    "job_id": "test_001",
    "company": "OpenAI",
    "title": "Business Analyst",
    "location": "Jakarta",
    "url": "https://example.com",
    "source": "Manual Test",
    "match_status": "YES",
    "match_score": 95,
    "match_reasons": "Testing Google Sheets integration",
    "matched_skills": "SQL, Python, ERP"
}

success = manager.add_job(job)

print("Success:", success)