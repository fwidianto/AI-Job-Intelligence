"""
Email Notifier - Sends job alerts via email

Uses Gmail SMTP to send daily digest emails with new job matches.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailNotifier:
    """
    Sends email notifications for new job matches.
    
    Uses Gmail SMTP with App Password authentication.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize email notifier.
        
        Args:
            config: Email configuration dict with smtp_host, smtp_port,
                   smtp_user, smtp_password, from_addr, to_addr
        """
        self.smtp_host = config.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_user = config.get('smtp_user', '')
        self.smtp_password = config.get('smtp_password', '')
        self.from_addr = config.get('from_addr', self.smtp_user)
        self.to_addrs = config.get('to_addr', [self.smtp_user])
        self.enabled = config.get('enabled', True)
        
        self.logger = logging.getLogger(__name__)
    
    def send_job_alert(self, jobs: List[Dict[str, Any]], subject: str = None) -> bool:
        """
        Send email with new job matches.
        
        Args:
            jobs: List of job dictionaries
            subject: Optional email subject
            
        Returns:
            True if email sent successfully
        """
        if not self.enabled:
            self.logger.info("Email notifications disabled")
            return True
        
        if not jobs:
            self.logger.info("No jobs to send")
            return True
        
        if not self.smtp_user or not self.smtp_password:
            self.logger.warning("Email credentials not configured")
            return False
        
        # Generate subject
        if not subject:
            num_jobs = len(jobs)
            subject = f"🎯 {num_jobs} New Job Matches - {datetime.now().strftime('%b %d, %Y')}"
        
        # Generate email body
        body_html = self._generate_email_body(jobs)
        body_text = self._generate_text_body(jobs)
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_addr
        msg['To'] = ', '.join(self.to_addrs) if isinstance(self.to_addrs, list) else self.to_addrs
        
        # Attach text and HTML versions
        msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))
        
        # Send email
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            self.logger.info(f"Sent email with {len(jobs)} job matches")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
    
    def _generate_email_body(self, jobs: List[Dict[str, Any]]) -> str:
        """Generate HTML email body"""
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                         color: white; padding: 20px; border-radius: 10px 10px 0 0; }
                .header h1 { margin: 0; font-size: 24px; }
                .header p { margin: 10px 0 0 0; opacity: 0.9; }
                .job-card { background: #f9f9f9; border-left: 4px solid #667eea; 
                           margin: 15px 0; padding: 15px; border-radius: 5px; }
                .job-title { font-size: 18px; font-weight: bold; color: #333; margin: 0 0 5px 0; }
                .job-company { color: #667eea; font-weight: bold; margin: 0 0 10px 0; }
                .job-details { font-size: 14px; color: #666; }
                .job-score { display: inline-block; background: #4CAF50; color: white; 
                            padding: 3px 10px; border-radius: 15px; font-size: 12px; margin-right: 10px; }
                .job-skills { margin-top: 10px; }
                .skill-tag { display: inline-block; background: #e0e0e0; 
                            padding: 3px 8px; border-radius: 10px; font-size: 11px; margin: 2px; }
                .job-link { display: inline-block; background: #667eea; color: white; 
                           padding: 8px 15px; text-decoration: none; border-radius: 5px; 
                           margin-top: 10px; }
                .footer { background: #f0f0f0; padding: 15px; text-align: center; 
                         font-size: 12px; color: #666; border-radius: 0 0 10px 10px; }
                .summary { background: #fff3cd; padding: 10px; border-radius: 5px; 
                          margin: 10px 0; font-size: 14px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 New Job Matches Found</h1>
                    <p>{date}</p>
                </div>
                
                <div class="summary">
                    <strong>Summary:</strong> {num_jobs} new opportunities matching your profile
                </div>
                
                {jobs_html}
                
                <div class="footer">
                    <p>This is an automated notification from Job Intelligence Platform</p>
                    <p>Review your matches and take action!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Build jobs HTML
        jobs_html = ""
        for job in jobs:
            score = job.get('match_score', 0)
            score_color = '#4CAF50' if score >= 80 else '#FF9800' if score >= 50 else '#f44336'
            
            skills = job.get('matched_skills', '').split(', ') if job.get('matched_skills') else []
            skills_html = ''.join([f'<span class="skill-tag">{s}</span>' for s in skills if s])
            
            jobs_html += f"""
                <div class="job-card">
                    <div class="job-title">{job.get('title', 'Unknown Title')}</div>
                    <div class="job-company">{job.get('company', 'Unknown Company')}</div>
                    <div class="job-details">
                        <span class="job-score" style="background: {score_color}">{score}/100</span>
                        📍 {job.get('location', 'Not specified')}
                    </div>
                    <div class="job-details">
                        Match Reasons: {job.get('match_reasons', 'N/A')}
                    </div>
                    <div class="job-skills">
                        {skills_html}
                    </div>
                    <a class="job-link" href="{job.get('url', '#')}">View Job →</a>
                </div>
            """
        
        return html.format(
            date=datetime.now().strftime('%B %d, %Y'),
            num_jobs=len(jobs),
            jobs_html=jobs_html
        )
    
    def _generate_text_body(self, jobs: List[Dict[str, Any]]) -> str:
        """Generate plain text email body"""
        
        lines = [
            "=" * 60,
            "NEW JOB MATCHES FOUND",
            "=" * 60,
            "",
            f"Date: {datetime.now().strftime('%B %d, %Y')}",
            f"Total: {len(jobs)} new opportunities",
            "",
        ]
        
        for i, job in enumerate(jobs, 1):
            lines.append("-" * 60)
            lines.append(f"{i}. {job.get('title', 'Unknown')}")
            lines.append(f"   Company: {job.get('company', 'Unknown')}")
            lines.append(f"   Location: {job.get('location', 'Not specified')}")
            lines.append(f"   Score: {job.get('match_score', 0)}/100")
            lines.append(f"   URL: {job.get('url', 'N/A')}")
            lines.append(f"   Match: {job.get('match_reasons', 'N/A')}")
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("This is an automated notification.")
        lines.append("Review your matches and take action!")
        
        return '\n'.join(lines)
    
    def send_test_email(self) -> bool:
        """Send a test email"""
        test_job = {
            'title': 'Test Job - ERP Business Analyst',
            'company': 'Test Company',
            'location': 'Jakarta',
            'url': 'https://example.com/job',
            'match_score': 85,
            'match_reasons': 'Exact role match + SAP skills',
            'matched_skills': 'SAP, Odoo, SQL'
        }
        
        return self.send_job_alert([test_job], subject="[TEST] Job Intelligence Platform Email Test")


class MockEmailNotifier:
    """
    Mock email notifier for testing without sending real emails.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.enabled = config.get('enabled', True) if config else False
        self.logger = logging.getLogger(__name__)
    
    def send_job_alert(self, jobs: List[Dict[str, Any]], subject: str = None) -> bool:
        """Print email content instead of sending"""
        if not self.enabled:
            self.logger.info("Mock email: notifications disabled")
            return True
        
        print("\n" + "=" * 60)
        print("MOCK EMAIL NOTIFICATION")
        print("=" * 60)
        print(f"Subject: {subject or 'Job Alert'}")
        print(f"To: {len(jobs)} job(s)")
        print()
        
        for job in jobs:
            print(f"  📌 {job.get('title')} at {job.get('company')}")
            print(f"     Score: {job.get('match_score', 0)}/100 | {job.get('location')}")
            print(f"     URL: {job.get('url')}")
            print()
        
        print("=" * 60)
        return True
    
    def send_test_email(self) -> bool:
        return self.send_job_alert([{
            'title': 'Test Job',
            'company': 'Test Company',
            'location': 'Jakarta',
            'url': 'https://example.com',
            'match_score': 85,
            'match_reasons': 'Test match',
            'matched_skills': 'SAP, SQL'
        }], subject="[TEST] Mock Email Test")


def create_notifier(config: Dict[str, Any] = None) -> Any:
    """
    Factory function to create email notifier.
    
    Returns MockEmailNotifier if no credentials configured.
    """
    if not config or not config.get('smtp_user') or not config.get('smtp_password'):
        logger.warning("Email credentials not configured, using mock notifier")
        return MockEmailNotifier(config)
    
    return EmailNotifier(config)


def test_notifier():
    """Test the email notifier"""
    print("Testing Email Notifier...")
    
    # Test mock notifier
    notifier = MockEmailNotifier({'enabled': True})
    
    test_jobs = [
        {
            'title': 'ERP Business Analyst',
            'company': 'Unilever',
            'location': 'Jakarta',
            'url': 'https://unilever.greenhouse.io/jobs/123',
            'match_score': 92,
            'match_reasons': 'Exact role match + SAP + Odoo',
            'matched_skills': 'SAP ECC, Odoo ERP, SQL'
        },
        {
            'title': 'Business Operations Analyst',
            'company': 'Grab',
            'location': 'Remote',
            'url': 'https://grab.lever.co/jobs/456',
            'match_score': 85,
            'match_reasons': 'Operations role + SQL',
            'matched_skills': 'SQL, Business Intelligence'
        }
    ]
    
    notifier.send_job_alert(test_jobs)


if __name__ == "__main__":
    test_notifier()