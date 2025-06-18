"""SMTP Email Sender Test Utility.

Sends test emails to verify SMTP server functionality.
"""

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage


def send_test_email(subject=None, to_addr=None, from_addr=None):
    """Send a test email via SMTP server.
    
    Args:
        subject: Email subject line (auto-generated if None).
        to_addr: Recipient email address.
        from_addr: Sender email address.
        
    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    subject = subject or f"Test Email - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    to_addr = to_addr or "test@example.com"
    from_addr = from_addr or "sender@example.com"
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(f"""
    This is a test email sent via SMTP with STARTTLS.
    
    Timestamp: {datetime.now().isoformat()}
    From: {from_addr}
    To: {to_addr}
    
    If you receive this email, the SMTP server is working correctly.
    """)

    # Create SSL context for STARTTLS
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with smtplib.SMTP("localhost", 587) as server:
            server.starttls(context=context)
            server.send_message(msg)
        print(f"Test email sent successfully to {to_addr}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


if __name__ == "__main__":
    send_test_email()
