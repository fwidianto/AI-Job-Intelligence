"""
Google Sheets Integration - Read/Write job data to Google Sheets

This module handles:
- Authentication with Google Sheets API
- Creating/updating the Jobs sheet
- Tracking application status
- Analytics calculations
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import Google API libraries
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google API libraries not installed. Run: pip install google-api-python-client google-auth")


@dataclass
class SheetConfig:
    """Google Sheets configuration"""
    spreadsheet_id: str = ""
    credentials_file: str = "credentials/credentials.json"
    token_file: str = "credentials/token.json"
    sheets_service: Any = None  # Will be set after authentication


class SheetsManager:
    """
    Manages Google Sheets operations for job tracking.
    
    Sheet Structure:
    - Jobs: Discovered job opportunities
    - Applied: Tracking applications
    - Analytics: Dashboard metrics
    """
    
    # Sheet names
    SHEET_JOBS = "Jobs"
    SHEET_APPLIED = "Applied"
    SHEET_ANALYTICS = "Analytics"
    
    # Column headers for Jobs sheet
    JOBS_HEADERS = [
        "ID", "Date Found", "Company", "Job Title", "Location",
        "URL", "Source", "Match Status", "Match Score", "Match Reasons",
        "Matched Skills", "Applied", "Applied Date", "Interview", "Outcome", "Notes"
    ]
    
    def __init__(self, config: SheetConfig):
        """
        Initialize Sheets manager.
        
        Args:
            config: SheetConfig with spreadsheet_id and credentials
        """
        self.config = config
        self.service = None
        self.spreadsheet_id = config.spreadsheet_id
        
        if not GOOGLE_AVAILABLE:
            logger.error("Google API libraries not installed")
            return
            
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with Google Sheets API"""
        if not self.config.credentials_file:
            logger.error("No credentials file specified")
            return False
        
        creds = None
        
        # Check for existing token
        if os.path.exists(self.config.token_file):
            try:
                creds = Credentials.from_authorized_user_info(
                    self.config.token_file
                )
            except Exception:
                creds = None
        
        # If no valid credentials, try to refresh or get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None
            else:
                # Try to run OAuth flow (will open browser)
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.config.credentials_file,
                        ['https://www.googleapis.com/auth/spreadsheets']
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Failed to run OAuth flow: {e}")
                    return False
        
        # Save credentials for next time
        if creds and creds.valid:
            try:
                with open(self.config.token_file, 'w') as token:
                    token.write(creds.to_json())
            except Exception:
                pass
        
        # Build service
        if creds and creds.valid:
            try:
                self.service = build('sheets', 'v4', credentials=creds)
                logger.info("Successfully authenticated with Google Sheets")
                return True
            except Exception as e:
                logger.error(f"Failed to build Sheets service: {e}")
        
        return False
    
    def is_authenticated(self) -> bool:
        """Check if authenticated"""
        return self.service is not None
    
    def get_sheet_id(self, sheet_name: str) -> Optional[str]:
        """Get sheet ID by name"""
        if not self.service:
            return None
        
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            
            return None
        except HttpError as e:
            logger.error(f"Failed to get sheet ID: {e}")
            return None
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Get all jobs from the Jobs sheet.
        
        Returns:
            List of job dictionaries
        """
        if not self.service:
            logger.error("Not authenticated")
            return []
        
        try:
            range_name = f"{self.SHEET_JOBS}!A:P"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values or len(values) < 2:
                return []
            
            headers = values[0]
            jobs = []
            
            for row in values[1:]:
                if not row or not row[0]:
                    continue
                
                job = dict(zip(headers, row + [''] * (len(headers) - len(row))))
                jobs.append(job)
            
            return jobs
            
        except HttpError as e:
            logger.error(f"Failed to get jobs: {e}")
            return []
    
    def job_exists(self, job_id: str) -> bool:
        """
        Check if a job already exists in the sheet.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            True if job exists
        """
        jobs = self.get_all_jobs()
        return any(job.get('ID') == job_id for job in jobs)
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        """
        Add a new job to the Jobs sheet.
        
        Args:
            job_data: Dictionary with job information
            
        Returns:
            True if successful
        """
        if not self.service:
            logger.error("Not authenticated")
            return False
        
        try:
            # Prepare row data
            row = [
                job_data.get('job_id', ''),
                job_data.get('date_found', datetime.now().strftime('%Y-%m-%d')),
                job_data.get('company', ''),
                job_data.get('title', ''),
                job_data.get('location', ''),
                job_data.get('url', ''),
                job_data.get('source', ''),
                job_data.get('match_status', 'MAYBE'),
                str(job_data.get('match_score', 0)),
                job_data.get('match_reasons', ''),
                job_data.get('matched_skills', ''),
                'No',  # Applied
                '',    # Applied Date
                'No',  # Interview
                '',    # Outcome
                ''     # Notes
            ]
            
            # Append to sheet
            body = {
                'values': [row]
            }
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_JOBS}!A:P",
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            logger.info(f"Added job: {job_data.get('title')} at {job_data.get('company')}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to add job: {e}")
            return False
    
    def update_job_status(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update job status and fields.
        
        Args:
            job_id: Job ID to update
            updates: Dictionary with fields to update
            
        Returns:
            True if successful
        """
        if not self.service:
            logger.error("Not authenticated")
            return False
        
        try:
            # Find the row
            jobs = self.get_all_jobs()
            row_index = None
            
            for i, job in enumerate(jobs):
                if job.get('ID') == job_id:
                    row_index = i + 2  # +2 for header row and 1-based indexing
                    break
            
            if row_index is None:
                logger.warning(f"Job not found: {job_id}")
                return False
            
            # Build update data
            updates['Notes'] = updates.get('Notes', '') + f"\n[{datetime.now().strftime('%Y-%m-%d')}]"
            
            # Update each field
            for field, value in updates.items():
                col_index = self.JOBS_HEADERS.index(field) if field in self.JOBS_HEADERS else -1
                if col_index >= 0:
                    range_name = f"{self.SHEET_JOBS}!{chr(65 + col_index)}{row_index}"
                    body = {'values': [[value]]}
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='USER_ENTERED',
                        body=body
                    ).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update job: {e}")
            return False
    
    def get_new_matches(self, min_score: int = 80) -> List[Dict[str, Any]]:
        """
        Get new job matches above score threshold.
        
        Args:
            min_score: Minimum match score
            
        Returns:
            List of new matching jobs
        """
        jobs = self.get_all_jobs()
        new_matches = []
        
        for job in jobs:
            try:
                score = int(job.get('Match Score', 0))
                status = job.get('Match Status', '')
                applied = job.get('Applied', 'No')
                
                if score >= min_score and status == 'YES' and applied == 'No':
                    new_matches.append(job)
            except (ValueError, TypeError):
                continue
        
        return new_matches
    
    def get_analytics(self) -> Dict[str, Any]:
        """
        Get analytics summary from the sheet.
        
        Returns:
            Dictionary with analytics metrics
        """
        jobs = self.get_all_jobs()
        
        total_jobs = len(jobs)
        yes_matches = sum(1 for j in jobs if j.get('Match Status') == 'YES')
        maybe_matches = sum(1 for j in jobs if j.get('Match Status') == 'MAYBE')
        applied = sum(1 for j in jobs if j.get('Applied', '') == 'Yes')
        interviews = sum(1 for j in jobs if j.get('Interview', '') == 'Yes')
        
        # Calculate average score
        scores = []
        for job in jobs:
            try:
                score = int(job.get('Match Score', 0))
                if score > 0:
                    scores.append(score)
            except (ValueError, TypeError):
                continue
        
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return {
            'total_jobs': total_jobs,
            'yes_matches': yes_matches,
            'maybe_matches': maybe_matches,
            'applied': applied,
            'interviews': interviews,
            'average_score': round(avg_score, 1),
            'application_rate': round(applied / total_jobs * 100, 1) if total_jobs > 0 else 0,
            'interview_rate': round(interviews / applied * 100, 1) if applied > 0 else 0,
        }
    
    def create_spreadsheet(self, title: str = "Job Intelligence Platform") -> Optional[str]:
        """
        Create a new spreadsheet with proper sheet structure.
        
        Args:
            title: Spreadsheet title
            
        Returns:
            Spreadsheet ID or None
        """
        if not self.service:
            logger.error("Not authenticated")
            return None
        
        try:
            # Create spreadsheet
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            result = self.service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            spreadsheet_id = result.get('spreadsheetId')
            logger.info(f"Created spreadsheet: {spreadsheet_id}")
            
            # Set headers for Jobs sheet
            self._setup_jobs_sheet(spreadsheet_id)
            
            return spreadsheet_id
            
        except HttpError as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            return None
    
    def _setup_jobs_sheet(self, spreadsheet_id: str):
        """Setup the Jobs sheet with headers"""
        try:
            # Add headers
            body = {
                'values': [self.JOBS_HEADERS]
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{self.SHEET_JOBS}!A1:P1",
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            # Format headers (bold, background)
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    'requests': [{
                        'repeatCell': {
                            'range': {
                                'sheetId': 0,
                                'startRowIndex': 0,
                                'endRowIndex': 1,
                                'startColumnIndex': 0,
                                'endColumnIndex': len(self.JOBS_HEADERS)
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'textFormat': {
                                        'bold': True
                                    },
                                    'backgroundColor': {
                                        'red': 0.2,
                                        'green': 0.4,
                                        'blue': 0.8
                                    }
                                }
                            },
                            'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                        }
                    }]
                }
            ).execute()
            
            logger.info("Setup Jobs sheet headers")
            
        except HttpError as e:
            logger.error(f"Failed to setup sheet: {e}")


class MockSheetsManager:
    """
    Mock Sheets manager for testing without Google API.
    
    Stores data in memory for development/testing.
    """
    
    def __init__(self, config: SheetConfig = None):
        self.jobs = []
        self.next_id = 1
        logger.info("Using Mock Sheets Manager (no Google API)")
    
    def is_authenticated(self) -> bool:
        return True
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        return self.jobs
    
    def job_exists(self, job_id: str) -> bool:
        return any(j.get('ID') == job_id for j in self.jobs)
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        if 'job_id' not in job_data:
            job_data['job_id'] = str(self.next_id)
            self.next_id += 1
        
        self.jobs.append(job_data)
        print(f"[MOCK] Added job: {job_data.get('title')} at {job_data.get('company')}")
        return True
    
    def get_new_matches(self, min_score: int = 80) -> List[Dict[str, Any]]:
        return [j for j in self.jobs if j.get('match_score', 0) >= min_score]
    
    def get_analytics(self) -> Dict[str, Any]:
        total = len(self.jobs)
        return {
            'total_jobs': total,
            'yes_matches': sum(1 for j in self.jobs if j.get('match_status') == 'YES'),
            'applied': 0,
            'interviews': 0,
        }


def create_sheets_manager(config: SheetConfig = None) -> Any:
    """
    Factory function to create Sheets manager.
    
    Returns MockSheetsManager if Google API not available or no credentials.
    """
    if not GOOGLE_AVAILABLE or not config or not config.spreadsheet_id:
        logger.warning("Using Mock Sheets Manager (Google API not configured)")
        return MockSheetsManager(config)
    
    return SheetsManager(config)


def test_sheets():
    """Test the sheets manager"""
    print("Testing Sheets Manager...")
    
    # Create mock manager
    manager = MockSheetsManager()
    
    # Add a test job
    test_job = {
        'job_id': 'test_001',
        'title': 'ERP Business Analyst',
        'company': 'Unilever',
        'location': 'Jakarta',
        'url': 'https://example.com/job',
        'source': 'Greenhouse',
        'match_status': 'YES',
        'match_score': 85,
        'match_reasons': 'Exact role match + SAP skills',
        'matched_skills': 'SAP, Odoo, SQL'
    }
    
    manager.add_job(test_job)
    jobs = manager.get_all_jobs()
    
    print(f"Total jobs: {len(jobs)}")
    print(f"New matches: {len(manager.get_new_matches())}")


if __name__ == "__main__":
    test_sheets()