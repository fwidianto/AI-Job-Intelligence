"""
Google Sheets Integration - Read/Write job data to Google Sheets

This module handles:
- Authentication with Google Service Account (headless/scheduled environment)
- Creating/updating the Jobs sheet
- Tracking application status
- Analytics calculations

Authentication:
- Uses Google Service Account for server-to-server authentication
- No browser interaction required
- Suitable for scheduled Python scripts (Windows Task Scheduler)

Example setup:
1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a Service Account
4. Download the JSON key file
5. Share your spreadsheet with the service account email
6. Set credentials_file path in SheetConfig
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# =============================================================================
# GOOGLE API IMPORTS - Service Account Only
# =============================================================================

GOOGLE_AVAILABLE = False
_import_error: Optional[str] = None

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError as e:
    _import_error = str(e)
    logger.warning(
        "Google API libraries not installed. "
        "Run: pip install google-api-python-client google-auth"
    )


# =============================================================================
# CONSTANTS
# =============================================================================

# Google Sheets API scope
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Sheet names
SHEET_JOBS = "Jobs"
SHEET_APPLIED = "Applied"
SHEET_ANALYTICS = "Analytics"

# Column headers for Jobs sheet (0-indexed for column calculation)
JOBS_HEADERS = [
    "ID",             # 0
    "Date Found",     # 1
    "Company",        # 2
    "Job Title",      # 3
    "Location",       # 4
    "URL",            # 5
    "Source",         # 6
    "Match Status",   # 7
    "Match Score",    # 8
    "Match Reasons",  # 9
    "Matched Skills", # 10
    "Applied",        # 11
    "Applied Date",   # 12
    "Interview",      # 13
    "Outcome",        # 14
    "Notes"           # 15
]

# Column range for jobs (A:P = columns 0-15)
JOBS_RANGE = "A:P"
ID_COLUMN = "A"  # Column A for job IDs (efficient duplicate detection)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SheetConfig:
    """
    Google Sheets configuration for service account authentication.
    
    Attributes:
        spreadsheet_id: Google Sheets spreadsheet ID (from URL)
        credentials_file: Path to service account JSON key file
        
    Example:
        config = SheetConfig(
            spreadsheet_id="1ABC...xyz",
            credentials_file="credentials/service-account.json"
        )
    """
    spreadsheet_id: str = ""
    credentials_file: str = "credentials/credentials.json"


# =============================================================================
# SHEETS MANAGER - Google Service Account Authentication
# =============================================================================

class SheetsManager:
    """
    Manages Google Sheets operations for job tracking using Service Account.
    
    Sheet Structure:
    - Jobs: Discovered job opportunities
    - Applied: Tracking applications
    - Analytics: Dashboard metrics
    
    Features:
    - Service Account authentication (no browser required)
    - Efficient duplicate detection via get_existing_job_ids()
    - Batch updates for multiple cell changes
    - Structured logging
    - Case-insensitive analytics
    """
    
    def __init__(self, config: SheetConfig) -> None:
        """
        Initialize Sheets manager with Service Account authentication.
        
        Args:
            config: SheetConfig with spreadsheet_id and credentials_file
            
        Note:
            Authentication is performed immediately during initialization.
            Check is_authenticated() before making API calls.
        """
        self.config = config
        self.service = None
        self.spreadsheet_id = config.spreadsheet_id
        self._existing_job_ids: Optional[Set[str]] = None
        
        # Validate configuration
        if not GOOGLE_AVAILABLE:
            logger.error("Google API libraries not installed")
            return
            
        if not config.credentials_file:
            logger.error("Credentials file path not specified")
            return
            
        if not config.spreadsheet_id:
            logger.error("Spreadsheet ID not specified")
            return
        
        # Authenticate
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """
        Authenticate using Google Service Account.
        
        Uses google.oauth2.service_account.Credentials.from_service_account_file()
        
        Returns:
            True if authentication successful, False otherwise
        """
        credentials_path = self.config.credentials_file
        
        # Validate credentials file exists
        if not os.path.exists(credentials_path):
            logger.error(
                "Credentials file not found: '%s'",
                credentials_path
            )
            return False
        
        try:
            # Create credentials from service account file
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=SCOPES
            )
            
            # Build the Sheets service
            self.service = build("sheets", "v4", credentials=creds)
            
            logger.info("Successfully authenticated with Google Sheets (Service Account)")
            return True
            
        except FileNotFoundError:
            logger.error(
                "Credentials file not found: '%s'",
                credentials_path
            )
            return False
            
        except Exception as e:
            logger.error(
                "Failed to authenticate with Google Sheets: %s",
                str(e)
            )
            return False
    
    def is_authenticated(self) -> bool:
        """
        Check if authenticated with Google Sheets API.
        
        Returns:
            True if service is available and ready
        """
        return self.service is not None
    
    # =========================================================================
    # EFFICIENT DUPLICATE DETECTION
    # =========================================================================
    
    def get_existing_job_ids(self) -> Set[str]:
        """
        Efficiently fetch only job IDs from column A.
        
        This method is optimized for duplicate detection - it only fetches
        the ID column instead of the entire sheet, reducing API calls and
        improving performance.
        
        Returns:
            Set of existing job IDs (strings)
        """
        if not self.service:
            logger.error("Not authenticated - cannot fetch job IDs")
            return set()
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{SHEET_JOBS}!{ID_COLUMN}:{ID_COLUMN}"
            ).execute()
            
            values = result.get("values", [])
            
            if not values:
                return set()
            
            # Skip header row, extract job IDs
            job_ids = set()
            for row in values[1:]:  # Skip header
                if row and row[0]:  # Has ID
                    job_ids.add(row[0])
            
            logger.debug("Fetched %d existing job IDs", len(job_ids))
            return job_ids
            
        except HttpError as e:
            logger.error("Failed to fetch job IDs: %s", str(e))
            return set()
    
    def _refresh_job_ids_cache(self) -> None:
        """
        Refresh the internal cache of job IDs.
        
        Call this before batch operations to ensure cache is fresh.
        """
        self._existing_job_ids = self.get_existing_job_ids()
        logger.debug("Job IDs cache refreshed: %d IDs", len(self._existing_job_ids or set()))
    
    def job_exists(self, job_id: str) -> bool:
        """
        Check if a job already exists in the sheet.
        
        Uses cached job IDs for efficiency.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            True if job exists
        """
        if self._existing_job_ids is None:
            self._refresh_job_ids_cache()
        
        exists = job_id in (self._existing_job_ids or set())
        
        if exists:
            logger.debug("Job ID '%s' already exists", job_id)
        
        return exists
    
    # =========================================================================
    # DATA RETRIEVAL
    # =========================================================================
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Get all jobs from the Jobs sheet.
        
        Handles:
        - Empty sheet
        - Missing headers
        - Malformed rows
        
        Returns:
            List of job dictionaries with header keys
        """
        if not self.service:
            logger.error("Not authenticated - cannot fetch jobs")
            return []
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{SHEET_JOBS}!{JOBS_RANGE}"
            ).execute()
            
            values = result.get("values", [])
            
            # Handle empty sheet
            if not values:
                logger.info("Jobs sheet is empty")
                return []
            
            # Handle missing headers
            if len(values) < 1:
                logger.warning("Jobs sheet has no header row")
                return []
            
            headers = values[0]
            
            # Handle sheet with only headers
            if len(values) < 2:
                logger.info("Jobs sheet has only headers, no data")
                return []
            
            jobs = []
            for idx, row in enumerate(values[1:], start=2):  # Row 2 onwards (1-indexed)
                # Skip malformed rows (no ID)
                if not row or not row[0]:
                    logger.warning("Skipping malformed row %d: no ID", idx)
                    continue
                
                # Pad row to match header length
                padded_row = row + [""] * (len(headers) - len(row))
                job = dict(zip(headers, padded_row))
                jobs.append(job)
            
            logger.info("Retrieved %d jobs from sheet", len(jobs))
            return jobs
            
        except HttpError as e:
            logger.error("Failed to get jobs: %s", str(e))
            return []
    
    def get_sheet_id_by_name(self, sheet_name: str) -> Optional[str]:
        """
        Get the internal sheet ID by sheet name.
        
        Args:
            sheet_name: Name of the sheet (e.g., "Jobs")
            
        Returns:
            Sheet ID string or None if not found
        """
        if not self.service:
            return None
        
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            for sheet in spreadsheet.get("sheets", []):
                if sheet["properties"]["title"] == sheet_name:
                    return sheet["properties"]["sheetId"]
            
            return None
            
        except HttpError as e:
            logger.error("Failed to get sheet ID for '%s': %s", sheet_name, str(e))
            return None
    
    # =========================================================================
    # DATA WRITING
    # =========================================================================
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        """
        Add a new job to the Jobs sheet.
        
        Prevents duplicates by checking job ID before adding.
        
        Args:
            job_data: Dictionary with job information
            
        Returns:
            True if job was added, False if duplicate or error
        """
        if not self.service:
            logger.error("Not authenticated - cannot add job")
            return False
        
        job_id = job_data.get("job_id", "")
        
        if not job_id:
            logger.error("Cannot add job: missing job_id")
            return False
        
        # Check for duplicate
        if self.job_exists(job_id):
            logger.warning(
                "Job ID '%s' already exists - skipping duplicate",
                job_id
            )
            return False
        
        try:
            # Prepare row data in header order
            row = [
                job_id,                                           # 0: ID
                job_data.get("date_found", datetime.now().strftime("%Y-%m-%d")),  # 1: Date Found
                job_data.get("company", ""),                     # 2: Company
                job_data.get("title", ""),                       # 3: Job Title
                job_data.get("location", ""),                     # 4: Location
                job_data.get("url", ""),                          # 5: URL
                job_data.get("source", ""),                       # 6: Source
                job_data.get("match_status", "MAYBE"),           # 7: Match Status
                str(job_data.get("match_score", 0)),             # 8: Match Score
                job_data.get("match_reasons", ""),               # 9: Match Reasons
                job_data.get("matched_skills", ""),               # 10: Matched Skills
                "No",                                            # 11: Applied
                "",                                              # 12: Applied Date
                "No",                                            # 13: Interview
                "",                                              # 14: Outcome
                ""                                               # 15: Notes
            ]
            
            # Append to sheet
            body = {"values": [row]}
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{SHEET_JOBS}!{JOBS_RANGE}",
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            
            # Update cache
            if self._existing_job_ids is not None:
                self._existing_job_ids.add(job_id)
            
            logger.info(
                "Added job '%s' at '%s'",
                job_data.get("title", "Unknown"),
                job_data.get("company", "Unknown")
            )
            return True
            
        except HttpError as e:
            logger.error("Failed to add job '%s': %s", job_id, str(e))
            return False
    
    def update_job_status(
        self,
        job_id: str,
        updates: Dict[str, Any],
        append_timestamp: bool = True
    ) -> bool:
        """
        Update job status and fields using batch updates.
        
        Args:
            job_id: Job ID to update
            updates: Dictionary with field names and values
            append_timestamp: If True, appends timestamp to Notes field
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            logger.error("Not authenticated - cannot update job")
            return False
        
        try:
            # Find the job row
            jobs = self.get_all_jobs()
            row_index = None
            
            for idx, job in enumerate(jobs, start=2):  # Row 2 onwards
                if job.get("ID") == job_id:
                    row_index = idx
                    break
            
            if row_index is None:
                logger.warning("Job not found for update: '%s'", job_id)
                return False
            
            # Build batch data
            batch_data = []
            
            for field_name, value in updates.items():
                if field_name not in JOBS_HEADERS:
                    continue
                    
                col_index = JOBS_HEADERS.index(field_name)
                col_letter = chr(65 + col_index)  # A=0 -> A, B=1 -> B, etc.
                
                # Handle Notes timestamp
                if field_name == "Notes" and append_timestamp:
                    timestamp = datetime.now().strftime("%Y-%m-%d")
                    value = f"[{timestamp}] {value}"
                
                batch_data.append({
                    "range": f"{SHEET_JOBS}!{col_letter}{row_index}",
                    "values": [[value]]
                })
            
            if not batch_data:
                logger.warning("No valid fields to update for job '%s'", job_id)
                return False
            
            # Execute batch update
            body = {
                "valueInputOption": "USER_ENTERED",
                "data": batch_data
            }
            
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.info(
                "Updated job '%s' with %d fields",
                job_id,
                len(batch_data)
            )
            return True
            
        except HttpError as e:
            logger.error("Failed to update job '%s': %s", job_id, str(e))
            return False
    
    # =========================================================================
    # ANALYTICS
    # =========================================================================
    
    def get_new_matches(self, min_score: int = 80) -> List[Dict[str, Any]]:
        """
        Get new job matches above score threshold.
        
        Uses case-insensitive comparison for status fields.
        
        Args:
            min_score: Minimum match score (default: 80)
            
        Returns:
            List of new matching jobs
        """
        jobs = self.get_all_jobs()
        new_matches = []
        
        for job in jobs:
            try:
                score = int(job.get("Match Score", 0))
                status = job.get("Match Status", "").upper()
                applied = job.get("Applied", "").upper()
                
                if score >= min_score and status == "YES" and applied == "NO":
                    new_matches.append(job)
                    
            except (ValueError, TypeError) as e:
                logger.debug("Skipping job due to parse error: %s", str(e))
                continue
        
        return new_matches
    
    def get_analytics(self) -> Dict[str, Any]:
        """
        Get analytics summary from the sheet.
        
        Uses case-insensitive comparison for status fields.
        
        Returns:
            Dictionary with analytics metrics
        """
        jobs = self.get_all_jobs()
        
        if not jobs:
            return {
                "total_jobs": 0,
                "yes_matches": 0,
                "maybe_matches": 0,
                "applied": 0,
                "interviews": 0,
                "average_score": 0.0,
                "application_rate": 0.0,
                "interview_rate": 0.0,
            }
        
        # Count using case-insensitive comparison
        yes_matches = 0
        maybe_matches = 0
        applied_count = 0
        interviews_count = 0
        scores = []
        
        for job in jobs:
            # Match Status
            status = job.get("Match Status", "").upper()
            if status == "YES":
                yes_matches += 1
            elif status == "MAYBE":
                maybe_matches += 1
            
            # Applied (case-insensitive)
            applied = job.get("Applied", "").upper()
            if applied == "YES":
                applied_count += 1
            
            # Interview (case-insensitive)
            interview = job.get("Interview", "").upper()
            if interview == "YES":
                interviews_count += 1
            
            # Score for average
            try:
                score = int(job.get("Match Score", 0))
                if score > 0:
                    scores.append(score)
            except (ValueError, TypeError):
                pass
        
        total_jobs = len(jobs)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        application_rate = (applied_count / total_jobs * 100) if total_jobs > 0 else 0.0
        interview_rate = (interviews_count / applied_count * 100) if applied_count > 0 else 0.0
        
        return {
            "total_jobs": total_jobs,
            "yes_matches": yes_matches,
            "maybe_matches": maybe_matches,
            "applied": applied_count,
            "interviews": interviews_count,
            "average_score": round(avg_score, 1),
            "application_rate": round(application_rate, 1),
            "interview_rate": round(interview_rate, 1),
        }
    
    # =========================================================================
    # SPREADSHEET MANAGEMENT
    # =========================================================================
    
    def create_spreadsheet(self, title: str = "Job Intelligence Platform") -> Optional[str]:
        """
        Create a new spreadsheet with proper sheet structure.
        
        Args:
            title: Spreadsheet title
            
        Returns:
            Spreadsheet ID or None
        """
        if not self.service:
            logger.error("Not authenticated - cannot create spreadsheet")
            return None
        
        try:
            spreadsheet = {"properties": {"title": title}}
            
            result = self.service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            spreadsheet_id = result.get("spreadsheetId")
            
            logger.info(
                "Created spreadsheet '%s' with ID: %s",
                title,
                spreadsheet_id
            )
            
            # Setup headers
            self._setup_jobs_sheet(spreadsheet_id)
            
            return spreadsheet_id
            
        except HttpError as e:
            logger.error("Failed to create spreadsheet: %s", str(e))
            return None
    
    def _setup_jobs_sheet(self, spreadsheet_id: str) -> None:
        """
        Setup the Jobs sheet with headers and formatting.
        
        Args:
            spreadsheet_id: ID of the spreadsheet to setup
        """
        try:
            # Write headers
            body = {"values": [JOBS_HEADERS]}
            
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{SHEET_JOBS}!A1:P1",
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            
            # Format headers (bold with background color)
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [{
                        "repeatCell": {
                            "range": {
                                "sheetId": 0,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": len(JOBS_HEADERS)
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True},
                                    "backgroundColor": {
                                        "red": 0.2,
                                        "green": 0.4,
                                        "blue": 0.8
                                    }
                                }
                            },
                            "fields": "userEnteredFormat(textFormat,backgroundColor)"
                        }
                    }]
                }
            ).execute()
            
            logger.info("Setup Jobs sheet headers")
            
        except HttpError as e:
            logger.error("Failed to setup sheet: %s", str(e))


# =============================================================================
# MOCK SHEETS MANAGER - For Testing Without Google API
# =============================================================================

class MockSheetsManager:
    """
    Mock Sheets manager for testing without Google API.
    
    Stores data in memory for development and testing.
    Maintains consistency with SheetsManager interface and data format.
    """
    
    def __init__(self, config: SheetConfig = None) -> None:
        """
        Initialize mock manager.
        
        Args:
            config: Optional SheetConfig (ignored in mock)
        """
        self.jobs: List[Dict[str, Any]] = []
        self._existing_job_ids: Set[str] = set()
        self._next_id = 1
        logger.info("Using Mock Sheets Manager (no Google API)")
    
    def is_authenticated(self) -> bool:
        """Always returns True for mock."""
        return True
    
    def get_existing_job_ids(self) -> Set[str]:
        """Get all job IDs from mock storage."""
        return set(j.get("ID", j.get("job_id", "")) for j in self.jobs)
    
    def _refresh_job_ids_cache(self) -> None:
        """Refresh the job IDs cache (no-op for mock)."""
        self._existing_job_ids = self.get_existing_job_ids()
    
    def job_exists(self, job_id: str) -> bool:
        """Check if job ID exists in mock storage."""
        return any(
            j.get("ID", j.get("job_id", "")) == job_id
            for j in self.jobs
        )
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Return all jobs from mock storage."""
        return list(self.jobs)
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        """
        Add a job to mock storage.
        
        Uses "ID" key to match SheetsManager format.
        """
        job_id = job_data.get("job_id") or job_data.get("ID", "")
        
        if not job_id:
            logger.error("Cannot add job: missing job_id")
            return False
        
        if self.job_exists(job_id):
            logger.warning(
                "Job ID '%s' already exists - skipping duplicate",
                job_id
            )
            return False
        
        # Normalize to "ID" key format
        normalized_job = dict(job_data)
        if "job_id" in normalized_job:
            normalized_job["ID"] = normalized_job.pop("job_id")
        
        self.jobs.append(normalized_job)
        
        logger.info(
            "Added job '%s' at '%s'",
            normalized_job.get("Job Title", "Unknown"),
            normalized_job.get("Company", "Unknown")
        )
        return True
    
    def update_job_status(
        self,
        job_id: str,
        updates: Dict[str, Any],
        append_timestamp: bool = True
    ) -> bool:
        """
        Update a job in mock storage.
        
        Args:
            job_id: Job ID to update
            updates: Dictionary with field names and values
            append_timestamp: If True, appends timestamp to Notes
            
        Returns:
            True if successful, False if job not found
        """
        for job in self.jobs:
            current_id = job.get("ID", job.get("job_id", ""))
            if current_id == job_id:
                for field, value in updates.items():
                    if append_timestamp and field == "Notes":
                        existing_notes = job.get("Notes", "")
                        timestamp = datetime.now().strftime("%Y-%m-%d")
                        job[field] = f"{existing_notes}\n[{timestamp}] {value}"
                    else:
                        job[field] = value
                
                logger.info("Updated job '%s'", job_id)
                return True
        
        logger.warning("Job not found for update: '%s'", job_id)
        return False
    
    def get_new_matches(self, min_score: int = 80) -> List[Dict[str, Any]]:
        """
        Get new matches using case-insensitive comparison.
        
        Args:
            min_score: Minimum match score
            
        Returns:
            List of matching jobs
        """
        matches = []
        
        for job in self.jobs:
            try:
                score = int(job.get("Match Score", job.get("match_score", 0)))
                status = job.get("Match Status", job.get("match_status", "")).upper()
                applied = job.get("Applied", job.get("applied", "")).upper()
                
                if score >= min_score and status == "YES" and applied == "NO":
                    matches.append(job)
            except (ValueError, TypeError):
                continue
        
        return matches
    
    def get_analytics(self) -> Dict[str, Any]:
        """
        Get analytics using case-insensitive comparison.
        
        Returns:
            Dictionary with analytics metrics
        """
        if not self.jobs:
            return {
                "total_jobs": 0,
                "yes_matches": 0,
                "maybe_matches": 0,
                "applied": 0,
                "interviews": 0,
                "average_score": 0.0,
                "application_rate": 0.0,
                "interview_rate": 0.0,
            }
        
        yes_matches = 0
        maybe_matches = 0
        applied_count = 0
        interviews_count = 0
        scores = []
        
        for job in self.jobs:
            status = job.get("Match Status", job.get("match_status", "")).upper()
            if status == "YES":
                yes_matches += 1
            elif status == "MAYBE":
                maybe_matches += 1
            
            applied = job.get("Applied", job.get("applied", "")).upper()
            if applied == "YES":
                applied_count += 1
            
            interview = job.get("Interview", job.get("interview", "")).upper()
            if interview == "YES":
                interviews_count += 1
            
            try:
                score = int(job.get("Match Score", job.get("match_score", 0)))
                if score > 0:
                    scores.append(score)
            except (ValueError, TypeError):
                pass
        
        total_jobs = len(self.jobs)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        application_rate = (applied_count / total_jobs * 100) if total_jobs > 0 else 0.0
        interview_rate = (interviews_count / applied_count * 100) if applied_count > 0 else 0.0
        
        return {
            "total_jobs": total_jobs,
            "yes_matches": yes_matches,
            "maybe_matches": maybe_matches,
            "applied": applied_count,
            "interviews": interviews_count,
            "average_score": round(avg_score, 1),
            "application_rate": round(application_rate, 1),
            "interview_rate": round(interview_rate, 1),
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_sheets_manager(config: Optional[SheetConfig] = None) -> Any:
    """
    Factory function to create the appropriate Sheets manager.
    
    Returns:
        - SheetsManager if Google API available and config valid
        - MockSheetsManager if Google API not available or config incomplete
    
    Args:
        config: SheetConfig with spreadsheet_id and credentials_file
        
    Example:
        config = SheetConfig(
            spreadsheet_id="1ABC...xyz",
            credentials_file="credentials/service-account.json"
        )
        manager = create_sheets_manager(config)
    """
    if not GOOGLE_AVAILABLE:
        logger.warning(
            "Google API libraries not available - using MockSheetsManager"
        )
        return MockSheetsManager(config)
    
    if not config:
        logger.warning("No config provided - using MockSheetsManager")
        return MockSheetsManager(config)
    
    if not config.spreadsheet_id:
        logger.warning("Spreadsheet ID not configured - using MockSheetsManager")
        return MockSheetsManager(config)
    
    if not config.credentials_file:
        logger.warning("Credentials file not configured - using MockSheetsManager")
        return MockSheetsManager(config)
    
    manager = SheetsManager(config)
    
    if not manager.is_authenticated():
        logger.warning(
            "Authentication failed - using MockSheetsManager"
        )
        return MockSheetsManager(config)
    
    return manager


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_sheets() -> None:
    """Test the sheets manager functionality."""
    print("=" * 60)
    print("Testing Sheets Manager")
    print("=" * 60)
    
    # Test with Mock Manager
    print("\n[MOCK] Testing MockSheetsManager...")
    
    manager = MockSheetsManager()
    
    # Test add_job
    test_jobs = [
        {
            "job_id": "gh_12345",
            "title": "ERP Business Analyst",
            "company": "Unilever",
            "location": "Jakarta",
            "url": "https://unilever.greenhouse.io/jobs/12345",
            "source": "Greenhouse",
            "match_status": "YES",
            "match_score": 92,
            "match_reasons": "Exact role match + SAP skills",
            "matched_skills": "SAP, Odoo, SQL",
        },
        {
            "job_id": "lev_67890",
            "title": "Business Operations Analyst",
            "company": "Grab",
            "location": "Remote",
            "url": "https://grab.lever.co/jobs/67890",
            "source": "Lever",
            "match_status": "YES",
            "match_score": 85,
            "match_reasons": "Operations role + SQL",
            "matched_skills": "SQL, Business Intelligence",
        },
    ]
    
    for job in test_jobs:
        success = manager.add_job(job)
        print(f"  Added job: {success}")
    
    # Test duplicate prevention
    print("\n[MOCK] Testing duplicate prevention...")
    duplicate_result = manager.add_job(test_jobs[0])
    print(f"  Duplicate add result: {duplicate_result} (expected: False)")
    
    # Test get_all_jobs
    print("\n[MOCK] Testing get_all_jobs...")
    jobs = manager.get_all_jobs()
    print(f"  Total jobs: {len(jobs)}")
    
    # Test get_new_matches
    print("\n[MOCK] Testing get_new_matches...")
    matches = manager.get_new_matches(min_score=80)
    print(f"  New matches (score >= 80): {len(matches)}")
    
    # Test analytics
    print("\n[MOCK] Testing analytics...")
    analytics = manager.get_analytics()
    print(f"  Total jobs: {analytics['total_jobs']}")
    print(f"  YES matches: {analytics['yes_matches']}")
    print(f"  Applied: {analytics['applied']}")
    print(f"  Average score: {analytics['average_score']}")
    
    # Test update_job_status
    print("\n[MOCK] Testing update_job_status...")
    update_result = manager.update_job_status(
        "gh_12345",
        {"Applied": "Yes", "Notes": "Applied via company website"}
    )
    print(f"  Update result: {update_result}")
    
    # Verify update
    jobs = manager.get_all_jobs()
    for job in jobs:
        if job.get("ID") == "gh_12345":
            print(f"  Applied status: {job.get('Applied')}")
            print(f"  Has notes: {'Notes' in job and job.get('Notes')}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_sheets()