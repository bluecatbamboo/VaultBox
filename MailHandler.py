"""SMTP Mail Handler for Email Processing.

Handles incoming SMTP messages, processes them, and queues them to Redis
for further processing by background workers.
"""

import asyncio
import datetime
import json
import logging
import os
import ssl
import uuid

import redis
from aiosmtpd.handlers import AsyncMessage
from aiosmtpd.smtp import SMTP

# Configure module logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/smtp.log"),
        logging.StreamHandler()
    ]
)


class SMTPHandler(AsyncMessage):
    """SMTP message handler with Redis queuing.
    
    Processes incoming SMTP messages and queues them to Redis for
    background processing and storage.
    """
    
    def __init__(self):
        """Initialize SMTP handler with Redis connection."""
        super().__init__()
        self._setup_redis()

    def _setup_redis(self) -> None:
        """Initialize Redis connection for message queuing."""
        self.redis = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=0
        )
        self.redis_queue = os.environ.get('REDIS_QUEUE', 'smtp_emails')
        self.redis_pubsub_prefix = os.environ.get('REDIS_PUBSUB_PREFIX', 'email_notify:')

    async def handle_message(self, message) -> None:
        """Process incoming email message and queue for storage.
        
        Args:
            message: Email message object from aiosmtpd.
        """
        # Generate unique email ID for tracking
        email_id = str(uuid.uuid4())[:23].replace('-', '')
        
        sender = message['From']
        recipient = message['To']
        subject = message['Subject'] or ""
        arrival_time = datetime.datetime.now().isoformat()

        # Extract message body based on content type
        if message.is_multipart():
            body = self._extract_multipart_body(message)
        else:
            body = self._extract_single_part_body(message)

        # Create email data structure
        email_data = {
            'id': email_id,
            'sender': sender,
            'recipient': recipient,
            'subject': subject,
            'body': body,
            'arrival_time': arrival_time,
            'is_read': False,
            'tags': [],
            'size_bytes': len(str(message))
        }

        try:
            # Queue email for database storage
            self.redis.rpush(self.redis_queue, json.dumps(email_data))
            
            # Publish real-time notification
            self._publish_notification(email_data)
            
            logger.info(f"[SMTP] Email {email_id} received from {sender} to {recipient}")
            logger.info(f"[SMTP] Subject: {subject}")
            
        except Exception as e:
            logger.error(f"[SMTP] Failed to queue email {email_id}: {e}")
            raise

    def _extract_multipart_body(self, message) -> str:
        """Extract body content from multipart message.
        
        Prefers text/plain over text/html content.
        
        Args:
            message: Multipart email message.
            
        Returns:
            str: Extracted message body.
        """
        body = None
        html_body = None
        
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                body = part.get_payload(decode=True)
                if body is not None:
                    body = body.decode(part.get_content_charset() or 'utf-8', errors='replace')
                    break
            elif part.get_content_type() == 'text/html' and html_body is None:
                html_body = part.get_payload(decode=True)
                if html_body is not None:
                    html_body = html_body.decode(part.get_content_charset() or 'utf-8', errors='replace')
        
        # Use text/plain if available, otherwise use text/html
        return body if body is not None else (html_body or "")

    def _extract_single_part_body(self, message) -> str:
        """Extract body content from single-part message.
        
        Args:
            message: Single-part email message.
            
        Returns:
            str: Extracted message body or empty string if extraction fails.
        """
        try:
            body = message.get_payload(decode=True)
            if body is not None:
                return body.decode(message.get_content_charset() or 'utf-8', errors='replace')
            else:
                return ""
        except Exception as e:
            logger.error(f"[SMTP] Error extracting single-part body: {e}")
            return ""

    def _publish_notification(self, email_data: dict) -> None:
        """Publish real-time email notification to Redis.
        
        Args:
            email_data: Email data dictionary.
        """
        try:
            pubsub_channel = f"{self.redis_pubsub_prefix}{email_data['recipient']}"
            notification_data = {
                'id': email_data['id'],
                'sender': email_data['sender'],
                'recipient': email_data['recipient'],
                'subject': email_data['subject'],
                'status': 'received',
                'arrival_time': email_data['arrival_time']
            }
            self.redis.publish(pubsub_channel, json.dumps(notification_data))
        except Exception as e:
            logger.error(f"[SMTP] Failed to publish notification: {e}")


async def start_smtp_server() -> None:
    """Start the SMTP server with TLS support.
    
    Configures and starts an SMTP server with STARTTLS on port 587.
    
    """
    import base64
    import tempfile
    
    # Base64-encoded certificates (required for both container and local development)
    ssl_cert_b64 = os.environ.get('SSL_CERT_BASE64')
    ssl_key_b64 = os.environ.get('SSL_KEY_BASE64')
    
    if not ssl_cert_b64 or not ssl_key_b64:
        raise ValueError(
            "SSL certificates are required as base64-encoded environment variables:\n"
            "SSL_CERT_BASE64 - Base64-encoded SSL certificate (required)\n"
            "SSL_KEY_BASE64 - Base64-encoded SSL private key (required)\n\n"
            "Generate certificates and encode them:\n"
            "  openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes\n"
            "  SSL_CERT_BASE64=$(base64 -w0 < cert.pem)\n"
            "  SSL_KEY_BASE64=$(base64 -w0 < key.pem)"
        )
    
    cert_path = None
    key_path = None
    temp_cert_file = None
    temp_key_file = None
    
    try:
        # Use base64-encoded certificates (create temporary files)
        logger.info("[SMTP] Using base64-encoded SSL certificates")
        
        # Decode certificate
        try:
            cert_data = base64.b64decode(ssl_cert_b64)
            temp_cert_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.pem', delete=False)
            temp_cert_file.write(cert_data)
            temp_cert_file.flush()
            cert_path = temp_cert_file.name
        except Exception as e:
            raise ValueError(f"Invalid SSL_CERT_BASE64: {e}")
        
        # Decode private key
        try:
            key_data = base64.b64decode(ssl_key_b64)
            temp_key_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.pem', delete=False)
            temp_key_file.write(key_data)
            temp_key_file.flush()
            key_path = temp_key_file.name
        except Exception as e:
            raise ValueError(f"Invalid SSL_KEY_BASE64: {e}")
        
        # Create SSL context
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        
        # Create and start server
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: SMTP(SMTPHandler(), require_starttls=True, tls_context=ssl_context),
            host="0.0.0.0",
            port=587
        )
        
        logger.info(f"[SMTP] Server starting on port 587 with STARTTLS")
        logger.info("[SMTP] Using base64-encoded SSL certificates")
            
        async with server:
            await server.serve_forever()
            
    finally:
        # Clean up temporary certificate files
        if temp_cert_file:
            try:
                os.unlink(temp_cert_file.name)
            except:
                pass
        if temp_key_file:
            try:
                os.unlink(temp_key_file.name)
            except:
                pass


if __name__ == "__main__":
    asyncio.run(start_smtp_server())
