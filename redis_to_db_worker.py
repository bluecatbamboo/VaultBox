"""Redis to Database Worker for Email Processing.

Background worker that processes emails from Redis queue and stores them
in the encrypted database.
"""

import json
import logging
import os

import redis

from email_db import EmailDB

# Configure module logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/worker.log"),
        logging.StreamHandler()
    ]
)


class EmailWorker:
    """Background worker to process emails from Redis queue to database.
    
    Continuously monitors Redis queue for incoming emails and stores them
    in the encrypted SQLite database.
    """
    
    def __init__(self):
        """Initialize worker with Redis and database connections."""
        self.redis = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=0
        )
        self.queue_name = os.environ.get('REDIS_QUEUE', 'smtp_emails')
        encryption_key = os.environ.get('EMAIL_ENCRYPTION_KEY')
        self.db = EmailDB(db_path="data/emails.db", encryption_key=encryption_key)

    def process_emails(self) -> None:
        """Continuously process emails from Redis queue to database."""
        logger.info(f"[WORKER] Started. Listening on queue '{self.queue_name}'...")
        
        while True:
            try:
                # Block until email is available (timeout=0 means block indefinitely)
                item = self.redis.blpop(self.queue_name, timeout=0)
                if item:
                    _, data = item
                    self._process_single_email(data)
            except KeyboardInterrupt:
                logger.info("[WORKER] Shutting down...")
                break
            except Exception as e:
                logger.error(f"[WORKER] Unexpected error: {e}")

    def _process_single_email(self, data: bytes) -> None:
        """Process a single email from the queue and store in database.
        
        Args:
            data: JSON-encoded email data from Redis queue.
        """
        try:
            email = json.loads(data)
            
            # Store email in database using provided ID
            email_id = self.db.insert_email_with_id(
                email_id=email['id'],
                sender=email['sender'],
                recipient=email['recipient'],
                subject=email['subject'],
                body=email['body'],
                arrival_time=email['arrival_time']
            )
            
            logger.info(f"[WORKER] Email {email_id} saved: {email['sender']} -> {email['recipient']}")
            
        except json.JSONDecodeError as e:
            logger.error(f"[WORKER] Invalid JSON data: {e}")
        except Exception as e:
            logger.error(f"[WORKER] Error processing email: {e}")

    def close(self) -> None:
        """Clean up resources."""
        if hasattr(self, 'db') and self.db:
            self.db.close()


def main() -> None:
    """Main worker entry point."""
    worker = EmailWorker()
    try:
        worker.process_emails()
    finally:
        worker.close()


if __name__ == "__main__":
    main()
