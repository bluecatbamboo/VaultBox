"""HTML Email Test for SMTP Server.

Tests sending HTML-only emails to verify SMTP server handles different content types.
"""

import random
import smtplib
import ssl
import string
import unittest
from datetime import datetime
from email.message import EmailMessage


def random_string(length=8):
    """Generate random alphanumeric string.
    
    Args:
        length: Length of string to generate.
        
    Returns:
        str: Random string of specified length.
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class TestSendHtmlOnlyEmail(unittest.TestCase):
    smtp_port = 587  # Default port

    def test_send_html_only(self):
        now = datetime.now()
        rand_id = random_string(12)
        subject = f"HTML Only Test - {now.strftime('%Y-%m-%d %H:%M:%S')} - {rand_id}"
        to_addr = f"test+{random_string(5)}@example.com"
        from_addr = f"sender+{random_string(5)}@example.com"
        html_body = f"""
          <div style='font-family: Arial, sans-serif;'>
            <h2 style='color:#dc3545;'>HTML Only Email</h2>
            <p>This is a <b>test email</b> with <span style='color:#28a745;'>only HTML</span> content.</p>
            <ul>
              <li><b>Timestamp:</b> {now.isoformat()}</li>
              <li><b>Random ID:</b> {rand_id}</li>
              <li><b>From:</b> {from_addr}</li>
              <li><b>To:</b> {to_addr}</li>
            </ul>
            <p style='color:#888;'>If you receive this email, the SMTP server is working correctly.</p>
          </div>
        """
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.add_alternative(html_body, subtype="html")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            with smtplib.SMTP("localhost", self.smtp_port) as server:
                server.starttls(context=context)
                server.send_message(msg)
            print(f"HTML only test email sent successfully to {to_addr} (port {self.smtp_port})")
            result = True
        except Exception as e:
            print(f"Failed to send HTML only email: {e}")
            result = False
        self.assertTrue(result, "Failed to send HTML only email")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Send an HTML-only test email to VaultBox SMTP server.")
    parser.add_argument('--port', type=int, default=587, help='SMTP server port (default: 587)')
    args, remaining = parser.parse_known_args()
    # Set the port on the class before running tests
    TestSendHtmlOnlyEmail.smtp_port = args.port
    import sys
    sys.argv = [sys.argv[0]] + remaining
    unittest.main()
