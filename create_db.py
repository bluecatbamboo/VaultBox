"""Database Creation Utility.

Creates the encrypted SQLite database for email storage.
"""

import os

from email_db import EmailDB


def create_db():
    """Create the email database and ensure data directory exists."""
    # Ensure the data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Create the database file if it doesn't exist
    db = EmailDB(db_path='data/emails.db')
    print('Database created at data/emails.db')
    db.close()


if __name__ == "__main__":
    create_db()
