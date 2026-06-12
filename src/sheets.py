"""
Google Sheets Integration with Dynamic Schema Management

This module provides:
- Dynamic schema management for Google Sheets
- Auto-creation of sheets and columns
- Schema discovery from existing sheets
- Support for multiple sheets (Jobs, Applications, Analytics, Companies, Interviews)
- Backward compatibility with existing data

Architecture:
- SheetSchemaManager: Handles schema discovery and synchronization
- DynamicSheetsManager: Main interface for all sheet operations
- Auto-migration of existing sheets to new schemas

Key Features:
- No hardcoded column references - reads from row 1
- Auto-creates missing columns when new fields appear
- Auto-creates missing sheets on first access
- Caches schema for performance
- Comprehensive logging
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# =============================================================================
# GOOGLE API IMPORTS
# =============================================================================

GOOGLE_AVAILABLE = False

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    logger.warning(
        "Google API libraries not installed. "
        "Run: pip install google-api-python-client google-auth"
    )


# =============================================================================
# CONSTANTS
# =============================================================================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetName(Enum):
    """Supported sheet names"""
    JOBS = "Jobs"
    APPLICATIONS = "Applications"
    ANALYTICS = "Analytics"
    COMPANIES = "Companies"
    INTERVIEWS = "Interviews"


# Default schemas for each sheet (used when creating new sheets)
DEFAULT_SCHEMAS: Dict[str, List[str]] = {
    SheetName.JOBS.value: [
        "ID", "Date Found", "Company", "Job Title", "Location",
        "URL", "Source", "Match Status", "Match Score", "Match Reasons",
        "Matched Skills", "Applied", "Applied Date", "Interview", "Outcome", "Notes"
    ],
    SheetName.APPLICATIONS.value: [
        "ID", "Job ID", "Company", "Job Title", "Applied Date",
        "Application Method", "Status", "Response Received", "Response Date",
        "Notes"
    ],
    SheetName.COMPANIES.value: [
        "Company Name", "Industry", "ATS Platform", "Career URL", "Jobs URL",
        "Priority", "Last Checked", "Jobs Found", "Active Jobs", "Notes"
    ],
    SheetName.INTERVIEWS.value: [
        "ID", "Application ID", "Company", "Job Title", "Interview Date",
        "Interview Type", "Interviewer", "Status", "Outcome", "Feedback", "Notes"
    ],
    SheetName.ANALYTICS.value: [
        "Metric", "Value", "Date Updated", "Notes"
    ]
}

# Field name used for ID column per sheet
ID_FIELDS: Dict[str, str] = {
    SheetName.JOBS.value: "ID",
    SheetName.APPLICATIONS.value: "ID",
    SheetName.COMPANIES.value: "Company Name",
    SheetName.INTERVIEWS.value: "ID",
    SheetName.ANALYTICS.value: "Metric"
}


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
        auto_create_sheets: If True, auto-create missing sheets
        auto_create_columns: If True, auto-create missing columns
    """
    spreadsheet_id: str = ""
    credentials_file: str = "credentials/credentials.json"
    auto_create_sheets: bool = True
    auto_create_columns: bool = True


# =============================================================================
# SCHEMA MANAGER
# =============================================================================

class SheetSchemaManager:
    """
    Manages dynamic schema for Google Sheets.
    
    Responsibilities:
    - Discover existing schema from sheet headers
    - Track column positions dynamically
    - Auto-create missing columns
    - Cache schema for performance
    """
    
    def __init__(self, service, spreadsheet_id: str):
        """
        Initialize schema manager.
        
        Args:
            service: Google Sheets API service
            spreadsheet_id: Spreadsheet ID
        """
        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self._schema_cache: Dict[str, List[str]] = {}
        self._column_indices: Dict[str, Dict[str, int]] = {}
        logger.debug("SheetSchemaManager initialized for spreadsheet: %s", spreadsheet_id)
    
    def get_headers(self, sheet_name: str) -> List[str]:
        """
        Get headers from sheet row 1.
        
        Args:
            sheet_name: Name of the sheet
            
        Returns:
            List of header names
        """
        if sheet_name in self._schema_cache:
            logger.debug("Returning cached headers for '%s'", sheet_name)
            return self._schema_cache[sheet_name]
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!1:1"
            ).execute()
            
            values = result.get("values", [])
            
            if not values:
                logger.info("No headers found for sheet '%s'", sheet_name)
                headers = []
            else:
                headers = values[0] if values else []
                logger.info(
                    "Discovered %d columns in sheet '%s': %s",
                    len(headers),
                    sheet_name,
                    headers[:5]
                )
            
            self._schema_cache[sheet_name] = headers
            self._column_indices[sheet_name] = {
                col: idx for idx, col in enumerate(headers)
            }
            
            return headers
            
        except HttpError as e:
            logger.error("Failed to get headers for '%s': %s", sheet_name, str(e))
            return []
    
    def get_column_index(self, sheet_name: str, column_name: str) -> Optional[int]:
        """
        Get the column index for a given column name.
        
        Args:
            sheet_name: Name of the sheet
            column_name: Name of the column
            
        Returns:
            Column index (0-based) or None if not found
        """
        if sheet_name not in self._column_indices:
            self.get_headers(sheet_name)
        
        return self._column_indices.get(sheet_name, {}).get(column_name)
    
    def column_to_letter(self, col_index: int) -> str:
        """
        Convert column index to Excel letter (0=A, 1=B, 26=AA, etc.).
        
        Args:
            col_index: Column index (0-based)
            
        Returns:
            Excel column letter (e.g., "A", "Z", "AA")
        """
        result = ""
        col_index += 1
        while col_index > 0:
            col_index -= 1
            result = chr(65 + (col_index % 26)) + result
            col_index //= 26
        return result
    
    def add_column(self, sheet_name: str, column_name: str) -> bool:
        """
        Add a new column to the sheet.
        
        Args:
            sheet_name: Name of the sheet
            column_name: Name of the new column
            
        Returns:
            True if successful
        """
        try:
            headers = self.get_headers(sheet_name)
            new_col_index = len(headers)
            col_letter = self.column_to_letter(new_col_index)
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!{col_letter}1",
                valueInputOption="USER_ENTERED",
                body={"values": [[column_name]]}
            ).execute()
            
            headers.append(column_name)
            self._schema_cache[sheet_name] = headers
            self._column_indices[sheet_name] = {
                col: idx for idx, col in enumerate(headers)
            }
            
            logger.info(
                "Added column '%s' to sheet '%s' at position %d (%s)",
                column_name,
                sheet_name,
                new_col_index + 1,
                col_letter
            )
            return True
            
        except HttpError as e:
            logger.error(
                "Failed to add column '%s' to '%s': %s",
                column_name,
                sheet_name,
                str(e)
            )
            return False
    
    def ensure_columns(
        self,
        sheet_name: str,
        required_columns: List[str]
    ) -> List[str]:
        """
        Ensure all required columns exist in the sheet.
        
        Args:
            sheet_name: Name of the sheet
            required_columns: List of column names that must exist
            
        Returns:
            List of columns that were added
        """
        existing = set(self.get_headers(sheet_name))
        missing = [col for col in required_columns if col not in existing]
        added = []
        
        for col in missing:
            if self.add_column(sheet_name, col):
                added.append(col)
        
        if added:
            logger.info(
                "Ensured %d columns in '%s': %s",
                len(added),
                sheet_name,
                added
            )
        
        return added
    
    def get_or_create_headers(
        self,
        sheet_name: str,
        default_headers: List[str]
    ) -> List[str]:
        """
        Get existing headers or create from default schema.
        
        Args:
            sheet_name: Name of the sheet
            default_headers: Default headers to use if sheet is empty
            
        Returns:
            List of header names
        """
        headers = self.get_headers(sheet_name)
        
        if not headers:
            if default_headers:
                logger.info(
                    "Creating default headers for '%s': %s",
                    sheet_name,
                    default_headers[:5]
                )
                try:
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"{sheet_name}!A1:{self.column_to_letter(len(default_headers) - 1)}1",
                        valueInputOption="USER_ENTERED",
                        body={"values": [default_headers]}
                    ).execute()
                    
                    headers = default_headers
                    self._schema_cache[sheet_name] = headers
                    self._column_indices[sheet_name] = {
                        col: idx for idx, col in enumerate(headers)
                    }
                    
                except HttpError as e:
                    logger.error(
                        "Failed to create headers for '%s': %s",
                        sheet_name,
                        str(e)
                    )
            else:
                logger.warning(
                    "No headers found and no defaults for '%s'",
                    sheet_name
                )
        
        return headers
    
    def get_id_column_range(self, sheet_name: str) -> str:
        """
        Get range for efficient ID column fetch.
        
        Args:
            sheet_name: Name of the sheet
            
        Returns:
            Range string (e.g., "A:A" for first column)
        """
        id_field = ID_FIELDS.get(sheet_name, "ID")
        col_index = self.get_column_index(sheet_name, id_field)
        
        if col_index is None:
            col_index = 0
        
        col_letter = self.column_to_letter(col_index)
        return f"{col_letter}:{col_letter}"
    
    def clear_cache(self) -> None:
        """Clear schema cache to force re-read from sheet."""
        self._schema_cache.clear()
        self._column_indices.clear()
        logger.debug("Schema cache cleared")


# =============================================================================
# DYNAMIC SHEETS MANAGER
# =============================================================================

class DynamicSheetsManager:
    """
    Main interface for Google Sheets operations with dynamic schema.
    
    Features:
    - Dynamic column handling (no hardcoded references)
    - Auto-creation of sheets and columns
    - Efficient ID-based duplicate detection
    - Batch updates
    - Case-insensitive field matching
    """
    
    def __init__(self, config: SheetConfig) -> None:
        """
        Initialize DynamicSheetsManager.
        
        Args:
            config: SheetConfig with spreadsheet_id and credentials_file
        """
        self.config = config
        self.service = None
        self.spreadsheet_id = config.spreadsheet_id
        self.schema_manager: Optional[SheetSchemaManager] = None
        self._id_cache: Dict[str, Set[str]] = {}
        
        if not GOOGLE_AVAILABLE:
            logger.error("Google API libraries not installed")
            return
            
        if not config.credentials_file:
            logger.error("Credentials file path not specified")
            return
            
        if not config.spreadsheet_id:
            logger.error("Spreadsheet ID not specified")
            return
        
        self._authenticate()
        
        if self.service:
            self.schema_manager = SheetSchemaManager(self.service, self.spreadsheet_id)
    
    def _authenticate(self) -> bool:
        """Authenticate using Google Service Account."""
        credentials_path = self.config.credentials_file
        
        if not os.path.exists(credentials_path):
            logger.error("Credentials file not found: '%s'", credentials_path)
            return False
        
        try:
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=SCOPES
            )
            self.service = build("sheets", "v4", credentials=creds)
            logger.info("Authenticated with Google Sheets (Service Account)")
            return True
            
        except Exception as e:
            logger.error("Authentication failed: %s", str(e))
            return False
    
    def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return self.service is not None
    
    # =========================================================================
    # SHEET MANAGEMENT
    # =========================================================================
    
    def sheet_exists(self, sheet_name: str) -> bool:
        """Check if a sheet exists in the spreadsheet."""
        if not self.service:
            return False
        
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            for sheet in spreadsheet.get("sheets", []):
                if sheet["properties"]["title"] == sheet_name:
                    return True
            
            return False
            
        except HttpError as e:
            logger.error("Failed to check sheet existence: %s", str(e))
            return False
    
    def create_sheet(self, sheet_name: str, default_headers: List[str] = None) -> bool:
        """Create a new sheet in the spreadsheet."""
        if not self.service:
            logger.error("Not authenticated - cannot create sheet")
            return False
        
        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "requests": [{
                        "addSheet": {
                            "properties": {
                                "title": sheet_name,
                                "index": 0
                            }
                        }
                    }]
                }
            ).execute()
            
            logger.info("Created sheet: '%s'", sheet_name)
            
            if default_headers:
                self.ensure_headers(sheet_name, default_headers)
            
            return True
            
        except HttpError as e:
            logger.error("Failed to create sheet '%s': %s", sheet_name, str(e))
            return False
    
    def ensure_sheet(self, sheet_name: str, default_headers: List[str] = None) -> bool:
        """Ensure sheet exists, creating if necessary."""
        if self.sheet_exists(sheet_name):
            logger.debug("Sheet '%s' already exists", sheet_name)
            return True
        
        if self.config.auto_create_sheets:
            logger.info("Auto-creating sheet: '%s'", sheet_name)
            return self.create_sheet(sheet_name, default_headers)
        
        logger.warning("Sheet '%s' does not exist and auto_create is disabled", sheet_name)
        return False
    
    def ensure_headers(
        self,
        sheet_name: str,
        default_headers: List[str]
    ) -> List[str]:
        """Ensure sheet has required headers, creating if needed."""
        self.ensure_sheet(sheet_name, default_headers)
        
        headers = self.schema_manager.get_or_create_headers(
            sheet_name,
            default_headers
        )
        
        if self.config.auto_create_columns:
            self.schema_manager.ensure_columns(sheet_name, default_headers)
        
        return headers
    
    # =========================================================================
    # DATA OPERATIONS
    # =========================================================================
    
    def get_all_records(self, sheet_name: str) -> List[Dict[str, Any]]:
        """Get all records from a sheet with dynamic column mapping."""
        if not self.service or not self.schema_manager:
            logger.error("Not initialized - cannot fetch records")
            return []
        
        try:
            headers = self.schema_manager.get_headers(sheet_name)
            
            if not headers:
                logger.info("Sheet '%s' has no headers", sheet_name)
                return []
            
            range_name = f"{sheet_name}!A:{self.schema_manager.column_to_letter(len(headers) - 1)}"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get("values", [])
            
            if len(values) < 2:
                logger.debug("Sheet '%s' has no data rows", sheet_name)
                return []
            
            records = []
            for idx, row in enumerate(values[1:], start=2):
                if not row or not row[0]:
                    continue
                
                padded_row = row + [""] * (len(headers) - len(row))
                record = dict(zip(headers, padded_row))
                records.append(record)
            
            logger.info("Retrieved %d records from '%s'", len(records), sheet_name)
            return records
            
        except HttpError as e:
            logger.error("Failed to get records from '%s': %s", sheet_name, str(e))
            return []
    
    def record_exists(self, sheet_name: str, record_id: str) -> bool:
        """Check if a record exists by ID."""
        if sheet_name not in self._id_cache:
            self._refresh_id_cache(sheet_name)
        
        return record_id in self._id_cache.get(sheet_name, set())
    
    def _refresh_id_cache(self, sheet_name: str) -> None:
        """Refresh the ID cache for a sheet."""
        if not self.service or not self.schema_manager:
            return
        
        try:
            id_field = ID_FIELDS.get(sheet_name, "ID")
            range_name = f"{sheet_name}!{self.schema_manager.get_id_column_range(sheet_name)}"
            
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get("values", [])
            
            ids = set()
            for row in values[1:]:
                if row and row[0]:
                    ids.add(row[0])
            
            self._id_cache[sheet_name] = ids
            logger.debug("Cached %d IDs for sheet '%s'", len(ids), sheet_name)
            
        except HttpError as e:
            logger.error("Failed to refresh ID cache for '%s': %s", sheet_name, str(e))
            self._id_cache[sheet_name] = set()
    
    def add_record(
        self,
        sheet_name: str,
        record_data: Dict[str, Any],
        default_headers: List[str] = None
    ) -> bool:
        """Add a new record to a sheet."""
        if not self.service or not self.schema_manager:
            logger.error("Not initialized - cannot add record")
            return False
        
        id_field = ID_FIELDS.get(sheet_name, "ID")
        record_id = record_data.get(id_field, record_data.get("job_id", ""))
        
        if not record_id:
            logger.error("Cannot add record: missing ID field '%s'", id_field)
            return False
        
        if self.record_exists(sheet_name, record_id):
            logger.warning("Record '%s' already exists in '%s'", record_id, sheet_name)
            return False
        
        if default_headers:
            self.ensure_headers(sheet_name, default_headers)
        
        headers = self.schema_manager.get_headers(sheet_name)
        
        if not headers:
            logger.error("Sheet '%s' has no headers - cannot add record", sheet_name)
            return False
        
        row = []
        for header in headers:
            value = record_data.get(header)
            if value is None:
                for key, val in record_data.items():
                    if key.lower() == header.lower():
                        value = val
                        break
            row.append(value if value is not None else "")
        
        try:
            range_name = f"{sheet_name}!A:{self.schema_manager.column_to_letter(len(headers) - 1)}"
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": [row]}
            ).execute()
            
            if sheet_name in self._id_cache:
                self._id_cache[sheet_name].add(record_id)
            
            logger.info(
                "Added record '%s' to '%s'",
                record_id,
                sheet_name
            )
            return True
            
        except HttpError as e:
            logger.error("Failed to add record to '%s': %s", sheet_name, str(e))
            return False
    
    def update_record(
        self,
        sheet_name: str,
        record_id: str,
        updates: Dict[str, Any],
        append_timestamp: bool = True
    ) -> bool:
        """Update fields in an existing record."""
        if not self.service or not self.schema_manager:
            logger.error("Not initialized - cannot update record")
            return False
        
        try:
            records = self.get_all_records(sheet_name)
            row_index = None
            id_field = ID_FIELDS.get(sheet_name, "ID")
            
            for idx, record in enumerate(records):
                if record.get(id_field) == record_id:
                    row_index = idx + 2
                    break
            
            if row_index is None:
                logger.warning("Record '%s' not found in '%s'", record_id, sheet_name)
                return False
            
            batch_data = []
            
            for field_name, value in updates.items():
                col_index = self.schema_manager.get_column_index(sheet_name, field_name)
                
                if col_index is None:
                    headers = self.schema_manager.get_headers(sheet_name)
                    for idx, header in enumerate(headers):
                        if header.lower() == field_name.lower():
                            col_index = idx
                            break
                
                if col_index is not None:
                    if field_name.lower() == "notes" and append_timestamp:
                        existing = records[row_index - 2].get("Notes", "")
                        timestamp = datetime.now().strftime("%Y-%m-%d")
                        value = f"{existing}\n[{timestamp}] {value}"
                    
                    col_letter = self.schema_manager.column_to_letter(col_index)
                    batch_data.append({
                        "range": f"{sheet_name}!{col_letter}{row_index}",
                        "values": [[value]]
                    })
            
            if not batch_data:
                logger.warning("No valid fields to update for '%s'", record_id)
                return False
            
            body = {
                "valueInputOption": "USER_ENTERED",
                "data": batch_data
            }
            
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.info(
                "Updated record '%s' in '%s' with %d fields",
                record_id,
                sheet_name,
                len(batch_data)
            )
            return True
            
        except HttpError as e:
            logger.error("Failed to update record '%s': %s", record_id, str(e))
            return False
    
    # =========================================================================
    # ANALYTICS
    # =========================================================================
    
    def get_new_matches(self, min_score: int = 80) -> List[Dict[str, Any]]:
        """Get new job matches above score threshold."""
        jobs = self.get_all_records(SheetName.JOBS.value)
        matches = []
        
        for job in jobs:
            try:
                score = int(job.get("Match Score", 0))
                status = job.get("Match Status", "").upper()
                applied = job.get("Applied", "").upper()
                
                if score >= min_score and status == "YES" and applied == "NO":
                    matches.append(job)
            except (ValueError, TypeError):
                continue
        
        return matches
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get analytics summary."""
        jobs = self.get_all_records(SheetName.JOBS.value)
        
        if not jobs:
            return {
                "total_jobs": 0, "yes_matches": 0, "maybe_matches": 0,
                "applied": 0, "interviews": 0, "average_score": 0.0,
                "application_rate": 0.0, "interview_rate": 0.0
            }
        
        yes_matches = maybe_matches = applied_count = interviews_count = 0
        scores = []
        
        for job in jobs:
            status = job.get("Match Status", "").upper()
            if status == "YES":
                yes_matches += 1
            elif status == "MAYBE":
                maybe_matches += 1
            
            if job.get("Applied", "").upper() == "YES":
                applied_count += 1
            if job.get("Interview", "").upper() == "YES":
                interviews_count += 1
            
            try:
                score = int(job.get("Match Score", 0))
                if score > 0:
                    scores.append(score)
            except (ValueError, TypeError):
                pass
        
        total_jobs = len(jobs)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        return {
            "total_jobs": total_jobs,
            "yes_matches": yes_matches,
            "maybe_matches": maybe_matches,
            "applied": applied_count,
            "interviews": interviews_count,
            "average_score": round(avg_score, 1),
            "application_rate": round(applied_count / total_jobs * 100, 1) if total_jobs else 0.0,
            "interview_rate": round(interviews_count / applied_count * 100, 1) if applied_count else 0.0
        }
    
    # =========================================================================
    # BACKWARD COMPATIBILITY
    # =========================================================================
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Backward compatibility - get all jobs."""
        return self.get_all_records(SheetName.JOBS.value)
    
    def job_exists(self, job_id: str) -> bool:
        """Backward compatibility - check if job exists."""
        return self.record_exists(SheetName.JOBS.value, job_id)
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        """Backward compatibility - add a job."""
        return self.add_record(
            SheetName.JOBS.value,
            job_data,
            DEFAULT_SCHEMAS[SheetName.JOBS.value]
        )
    
    def update_job_status(self, job_id: str, updates: Dict[str, Any], append_timestamp: bool = True) -> bool:
        """Backward compatibility - update job status."""
        return self.update_record(SheetName.JOBS.value, job_id, updates, append_timestamp)
    
    def get_existing_job_ids(self) -> Set[str]:
        """Backward compatibility - get existing job IDs."""
        if SheetName.JOBS.value not in self._id_cache:
            self._refresh_id_cache(SheetName.JOBS.value)
        return self._id_cache.get(SheetName.JOBS.value, set())
    
    # =========================================================================
    # SPREADSHEET MANAGEMENT
    # =========================================================================
    
    def create_spreadsheet(self, title: str = "Job Intelligence Platform") -> Optional[str]:
        """Create a new spreadsheet with default sheets."""
        if not self.service:
            return None
        
        try:
            spreadsheet = {"properties": {"title": title}}
            result = self.service.spreadsheets().create(body=spreadsheet).execute()
            spreadsheet_id = result.get("spreadsheetId")
            
            logger.info("Created spreadsheet '%s' with ID: %s", title, spreadsheet_id)
            
            self.spreadsheet_id = spreadsheet_id
            self.schema_manager = SheetSchemaManager(self.service, spreadsheet_id)
            
            for sheet_name, headers in DEFAULT_SCHEMAS.items():
                self.create_sheet(sheet_name, headers)
            
            return spreadsheet_id
            
        except HttpError as e:
            logger.error("Failed to create spreadsheet: %s", str(e))
            return None


# =============================================================================
# MOCK MANAGER - For Testing
# =============================================================================

class MockDynamicSheetsManager:
    """Mock implementation for testing without Google API."""
    
    def __init__(self, config: SheetConfig = None) -> None:
        self.config = config
        self.sheets: Dict[str, List[Dict[str, Any]]] = {}
        self._id_cache: Dict[str, Set[str]] = {}
        logger.info("Using MockDynamicSheetsManager (no Google API)")
    
    def is_authenticated(self) -> bool:
        return True
    
    def get_all_records(self, sheet_name: str) -> List[Dict[str, Any]]:
        return list(self.sheets.get(sheet_name, []))
    
    def record_exists(self, sheet_name: str, record_id: str) -> bool:
        if sheet_name not in self._id_cache:
            self._id_cache[sheet_name] = set(
                r.get("ID", r.get("Company Name", "")) 
                for r in self.sheets.get(sheet_name, [])
            )
        return record_id in self._id_cache.get(sheet_name, set())
    
    def add_record(
        self,
        sheet_name: str,
        record_data: Dict[str, Any],
        default_headers: List[str] = None
    ) -> bool:
        id_field = ID_FIELDS.get(sheet_name, "ID")
        record_id = record_data.get(id_field, record_data.get("job_id", ""))
        
        if not record_id:
            logger.error("Missing ID field")
            return False
        
        if self.record_exists(sheet_name, record_id):
            logger.warning("Record '%s' already exists", record_id)
            return False
        
        # Normalize keys to proper format
        normalized = {}
        for key, value in record_data.items():
            # Handle common key variations
            if key == "job_id":
                normalized["ID"] = value
            elif key == "title":
                normalized["Job Title"] = value
            elif key == "company":
                normalized["Company"] = value
            elif key == "location":
                normalized["Location"] = value
            elif key == "url":
                normalized["URL"] = value
            elif key == "source":
                normalized["Source"] = value
            elif key == "match_status":
                normalized["Match Status"] = value
            elif key == "match_score":
                normalized["Match Score"] = str(value)
            elif key == "match_reasons":
                normalized["Match Reasons"] = value
            elif key == "matched_skills":
                normalized["Matched Skills"] = value
            elif key == "applied":
                normalized["Applied"] = value
            elif key == "applied_date":
                normalized["Applied Date"] = value
            elif key == "interview":
                normalized["Interview"] = value
            elif key == "outcome":
                normalized["Outcome"] = value
            elif key == "notes":
                normalized["Notes"] = value
            elif key == "date_found":
                normalized["Date Found"] = value
            else:
                normalized[key] = value
        
        if sheet_name not in self.sheets:
            self.sheets[sheet_name] = []
        self.sheets[sheet_name].append(normalized)
        
        if sheet_name in self._id_cache:
            self._id_cache[sheet_name].add(record_id)
        
        logger.info("Mock: Added record '%s' to '%s'", record_id, sheet_name)
        return True
    
    def update_record(
        self,
        sheet_name: str,
        record_id: str,
        updates: Dict[str, Any],
        append_timestamp: bool = True
    ) -> bool:
        for record in self.sheets.get(sheet_name, []):
            current_id = record.get("ID", record.get("Company Name", ""))
            if current_id == record_id:
                for field, value in updates.items():
                    if append_timestamp and field.lower() == "notes":
                        record[field] = f"{record.get('Notes', '')}\n{datetime.now().strftime('%Y-%m-%d')} {value}"
                    else:
                        record[field] = value
                logger.info("Mock: Updated record '%s'", record_id)
                return True
        return False
    
    def get_new_matches(self, min_score: int = 80) -> List[Dict[str, Any]]:
        matches = []
        for job in self.sheets.get(SheetName.JOBS.value, []):
            try:
                score = int(job.get("Match Score", 0))
                if score >= min_score and job.get("Match Status", "").upper() == "YES" and job.get("Applied", "").upper() == "NO":
                    matches.append(job)
            except (ValueError, TypeError):
                continue
        return matches
    
    def get_analytics(self) -> Dict[str, Any]:
        jobs = self.sheets.get(SheetName.JOBS.value, [])
        if not jobs:
            return {"total_jobs": 0, "yes_matches": 0, "maybe_matches": 0, "applied": 0, "interviews": 0, "average_score": 0.0, "application_rate": 0.0, "interview_rate": 0.0}
        
        yes = maybe = applied = interviews = 0
        scores = []
        for job in jobs:
            status = job.get("Match Status", "").upper()
            if status == "YES": yes += 1
            elif status == "MAYBE": maybe += 1
            if job.get("Applied", "").upper() == "YES": applied += 1
            if job.get("Interview", "").upper() == "YES": interviews += 1
            try:
                score = int(job.get("Match Score", 0))
                if score > 0:
                    scores.append(score)
            except (ValueError, TypeError):
                pass
        
        total = len(jobs)
        return {
            "total_jobs": total,
            "yes_matches": yes,
            "maybe_matches": maybe,
            "applied": applied,
            "interviews": interviews,
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "application_rate": round(applied / total * 100, 1) if total else 0.0,
            "interview_rate": round(interviews / applied * 100, 1) if applied else 0.0
        }
    
    # Backward compatibility
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        return self.get_all_records(SheetName.JOBS.value)
    
    def job_exists(self, job_id: str) -> bool:
        return self.record_exists(SheetName.JOBS.value, job_id)
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        return self.add_record(SheetName.JOBS.value, job_data, DEFAULT_SCHEMAS[SheetName.JOBS.value])
    
    def update_job_status(self, job_id: str, updates: Dict[str, Any], append_timestamp: bool = True) -> bool:
        return self.update_record(SheetName.JOBS.value, job_id, updates, append_timestamp)
    
    def get_existing_job_ids(self) -> Set[str]:
        if SheetName.JOBS.value not in self._id_cache:
            self._id_cache[SheetName.JOBS.value] = set(
                r.get("ID", "") for r in self.sheets.get(SheetName.JOBS.value, [])
            )
        return self._id_cache.get(SheetName.JOBS.value, set())


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_sheets_manager(config: Optional[SheetConfig] = None):
    """Factory function to create the appropriate Sheets manager."""
    if not GOOGLE_AVAILABLE:
        logger.warning("Google API libraries not available - using MockDynamicSheetsManager")
        return MockDynamicSheetsManager(config)
    
    if not config or not config.spreadsheet_id or not config.credentials_file:
        logger.warning("Incomplete config - using MockDynamicSheetsManager")
        return MockDynamicSheetsManager(config)
    
    manager = DynamicSheetsManager(config)
    
    if not manager.is_authenticated():
        logger.warning("Authentication failed - using MockDynamicSheetsManager")
        return MockDynamicSheetsManager(config)
    
    return manager


# Alias for backward compatibility
SheetsManager = DynamicSheetsManager
MockSheetsManager = MockDynamicSheetsManager


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_sheets() -> None:
    """Test the dynamic sheets manager."""
    print("=" * 60)
    print("Testing Dynamic Sheets Manager")
    print("=" * 60)
    
    manager = MockDynamicSheetsManager()
    
    print("\n[MOCK] Testing Jobs sheet operations...")
    
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
        },
    ]
    
    for job in test_jobs:
        success = manager.add_job(job)
        print(f"  Added job: {success}")
    
    print("\n[MOCK] Testing duplicate prevention...")
    duplicate = manager.add_job(test_jobs[0])
    print(f"  Duplicate add: {duplicate} (expected: False)")
    
    print("\n[MOCK] Testing get_all_jobs...")
    jobs = manager.get_all_jobs()
    print(f"  Total jobs: {len(jobs)}")
    
    print("\n[MOCK] Testing update_job_status...")
    update = manager.update_job_status("gh_12345", {"Applied": "Yes", "Notes": "Applied via website"})
    print(f"  Update result: {update}")
    
    print("\n[MOCK] Testing analytics...")
    analytics = manager.get_analytics()
    for key, value in analytics.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_sheets()