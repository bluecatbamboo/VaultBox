# VaultBox

A secure, fast mailbox server designed for safely testing (recieving) and viewing emails in development and CI environments. VaultBox helps developers capture, inspect, and manage test emails without risking real inboxes or exposing sensitive data.

## Contents

- [VaultBox](#vaultbox)
  - [Contents](#contents)
  - [Features](#features)
    - [Security Features](#security-features)
    - [Usability Features](#usability-features)
    - [Development \& Deployment Features](#development--deployment-features)
  - [Machine Support](#machine-support)
  - [Getting Started](#getting-started)
    - [1. Clone and Run Locally (macOS recommended)](#1-clone-and-run-locally-macos-recommended)
    - [2. Pull and Run the Docker Image](#2-pull-and-run-the-docker-image)
  - [System Design](#system-design)
    - [1. Mail Arrival and Processing Flow](#1-mail-arrival-and-processing-flow)
    - [2. Authentication Flow](#2-authentication-flow)
  - [Environment Variable Configuration](#environment-variable-configuration)
  - [User Model and SSE Subscription](#user-model-and-sse-subscription)
  - [Endpoints \& Access URLs](#endpoints--access-urls)
  - [Email Testing](#email-testing)
    - [Sending a Test Email](#sending-a-test-email)
    - [Sending an HTML-Only Test Email](#sending-an-html-only-test-email)
  - [Future Development \& Roadmap](#future-development--roadmap)
  - [License](#license)
  - [Team](#team)

## Features

### Security Features

- STARTTLS support for secure SMTP connections
- Encrypted storage of email data (using AES encryption)
- Tokenized and encrypted email search index for privacy
- TOTP (Time-based One-Time Password) two-factor authentication for UI login
- Secure password hashing (bcrypt)
- JWT-based API authentication
- Environment-based secret management for sensitive keys
- No default credentials or certificates in the image (user must provide their own)

### Usability Features

- REST API for searching and retrieving emails (powered by SQLite full-text search)
- Interactive API documentation with Swagger (can be toggled off)
- Real-time email updates in the web UI using Server-Sent Events (SSE)
- Redis-based queuing for efficient email processing and notifications (embedded Redis for local/CI use)
- Modern web interface for browsing, searching, and viewing emails (can be toggled off)
- Download email content and attachments directly from the UI
- Easy setup and deployment with Docker support
- Kubernetes/cloud-ready deployment (base64 certs, env config)
- User authentication and access control

### Development & Deployment Features

- Docker image with embedded Redis for easy local and CI/CD setup
- All configuration via environment variables (12-factor style)
- Base64-encoded SSL certificates for secure cloud/Kubernetes secrets
- No persistent secrets or credentials in the image
- Example configs for local, Docker, and Kubernetes deployments

## Machine Support

VaultBox is developed and tested primarily on macOS. While it may work on other operating systems, official support and troubleshooting are focused on macOS environments.

## Getting Started

You can set up VaultBox in two main ways:

### 1. Clone and Run Locally (macOS recommended)

```bash
git clone https://github.com/bluecatbamboo/VaultBox.git
cd VaultBox
pip install -r requirements.txt
# See the next section for environment variable setup
```

### 2. Pull and Run the Docker Image

```bash
docker pull ghcr.io/bluecatbamboo/vaultbox:latest
# See the next section for environment variable setup
```

For both methods, refer to the next section for required environment variable configuration.

## System Design

### 1. Mail Arrival and Processing Flow

- Incoming emails are received via the SMTP server (with STARTTLS support).
- Each email is placed onto a Redis queue and broadcast to connected web UI clients in real time (SSE).
- A background worker process consumes emails from the Redis queue, encrypts them, and saves them to the SQLite database.
- A tokenized, encrypted search index is generated for privacy-preserving search.
- The web UI and REST API provide access to search, view, and download emails.

### 2. Authentication Flow

- User credentials (username, bcrypt-hashed password, and TOTP secret) are provided via environment variables.
- Login to the web UI requires both password and TOTP code (2FA).
- Passwords are verified using bcrypt; TOTP codes are verified using pyotp.
- Upon successful login, a JWT access token is issued and stored in an HttpOnly cookie.
- API access is protected by JWT authentication (token required for all endpoints).
- All sensitive keys and secrets are managed via environment variables.

## Environment Variable Configuration

VaultBox requires several environment variables for secure operation. The same variables are used for both local and Docker runs, but the format for setting them differs:

- **Local run:** Set variables in a `.env` file or export them in your shell.
- **Docker run:** Pass variables using `-e` flags or with a `--env-file`.

**Essential environment variables:**

| Variable                | Description                                      |
|-------------------------|--------------------------------------------------|
| SECRET_KEY              | JWT signing key (**required**). Must be a 32-byte hex string (e.g., output of `openssl rand -hex 32`). |
| EMAIL_ENCRYPTION_KEY    | Email content encryption key (**required**). Must be a valid Fernet key (e.g., output of `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`). |
| EMAIL_UI_USERS          | Admin user credentials (username:hash:totp) (**required**) |
| SSL_CERT_BASE64         | Base64-encoded SSL certificate (**required**). Used for enabling STARTTLS on the SMTP server and HTTPS for the web UI. |
| SSL_KEY_BASE64          | Base64-encoded SSL private key (**required**). Used for enabling STARTTLS on the SMTP server and HTTPS for the web UI. |
| DATABASE_URL            | SQLite DB path (default: `sqlite:///./data/emails.db`) *(do not change unless needed)* |
| REDIS_URL               | Redis connection URL (default: `redis://localhost:6379`) *(do not change unless needed)* |
| ENABLE_SWAGGER          | Enable/disable Swagger docs (`true`/`false`)     |
| ENABLE_UI               | Enable/disable web UI (`true`/`false`)           |

*Most users should only set the required variables above. Other variables (like `DATABASE_URL` and `REDIS_URL`) should only be changed for advanced or custom setups.*

**Multiple Users:**
- You can specify multiple users in `EMAIL_UI_USERS` by separating each user entry with a semicolon (`;`).
- Format: `username:password_hash:totp_secret;username2:password_hash2:totp_secret2`

*Example for local run (.env):*
```env
SECRET_KEY=your-secret-key
EMAIL_ENCRYPTION_KEY=your-encryption-key
EMAIL_UI_USERS="admin:hash:totp"
SSL_CERT_BASE64=base64-encoded-cert
SSL_KEY_BASE64=base64-encoded-key
```

*Example for Docker run:*
```bash
docker run -e SECRET_KEY=your-secret-key \
  -e EMAIL_ENCRYPTION_KEY=your-encryption-key \
  -e EMAIL_UI_USERS="admin:hash:totp" \
  -e SSL_CERT_BASE64=base64-encoded-cert \
  -e SSL_KEY_BASE64=base64-encoded-key \
  ...
  ghcr.io/bluecatbamboo/vaultbox:latest
```

Or use a file:
```bash
docker run --env-file .env ghcr.io/bluecatbamboo/vaultbox:latest
```

See `.env.example` for a full list and details of all available variables.

<details>
<summary><strong>🔧 Utility Scripts for Generating Secrets and Credentials</strong></summary>

You can use the following scripts to generate the required secrets and credentials for your `.env` file or Docker environment variables:

**Generate a strong SECRET_KEY (hex):**
```bash
openssl rand -hex 32
```

**Generate an EMAIL_ENCRYPTION_KEY (Fernet key):**
```python
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

**Generate a bcrypt password hash:**
```python
python3 -c 'import bcrypt; print(bcrypt.hashpw(b"your_password", bcrypt.gensalt()).decode())'
```

**Generate a TOTP secret (for use with authenticator apps):**
```python
python3 -c 'import pyotp; print(pyotp.random_base32())'
```
- The TOTP secret can be added to popular authenticator apps like Google Authenticator, Microsoft Authenticator, Authy, etc.

**Generate base64-encoded SSL certificate and key:**
```bash
# Generate self-signed cert (for testing only)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
# Encode to base64
base64 -w0 < cert.pem > cert.pem.b64
base64 -w0 < key.pem > key.pem.b64
```

</details>

## User Model and SSE Subscription

**Note:** The "users" in VaultBox are not actual email recipients, but admin users who can view all incoming emails regardless of the "To" address. These users are defined for authentication and access control to the web UI and API.

For real-time updates via the SSE (Server-Sent Events) endpoint, clients must subscribe using a full email address. The SSE stream will only deliver updates for emails addressed to that specific address, allowing for targeted monitoring if needed.

## Endpoints & Access URLs

Once VaultBox is running, you can access the following endpoints:

- **Web UI:**  http://localhost:8001  (if ENABLE_UI is true)
- **API Documentation (Swagger):**  http://localhost:8001/docs  (if ENABLE_SWAGGER is true)
- **SMTP Server:**  localhost:587  (for sending test emails)
- **REST API Base:**  http://localhost:8001/api/
    - `/api/emails` — List/search emails
    - `/api/emails/{id}` — Get email by ID
    - `/api/me` — Get current user info
    - `/api/login` — Login (JWT)
    - `/api/logout` — Logout
    - `/api/sse/{email}` — Subscribe to real-time updates for a specific email address

Adjust the host/port as needed if you change the configuration.


## Email Testing

You can easily test VaultBox by sending emails to its SMTP server. Sample scripts are provided in the `testing/` folder to help you verify that the service is working correctly.

### Sending a Test Email

Run the following script to send a test email to VaultBox (make sure the VaultBox server is running):

```bash
python3 testing/send_test_email.py
```

This script will send a test email to `test@example.com` via the local SMTP server on port 587. You can customize the recipient, sender, and subject by editing the script or calling its function directly.

<details>
<summary><strong>Example Python Code: Send Plain Text Email</strong></summary>

```python
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

def send_test_email(subject=None, to_addr=None, from_addr=None):
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
```

</details>

### Sending an HTML-Only Test Email

To test sending an email with only HTML content, run:

```bash
python3 testing/test_send_html_only_email.py
```

This script will send an HTML-only email to a randomized test address. You can review the code or modify it as needed.

<details>
<summary><strong>Example Python Code: Send HTML-Only Email</strong></summary>

```python
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
import random
import string

def random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def send_html_only_email():
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
        with smtplib.SMTP("localhost", 587) as server:
            server.starttls(context=context)
            server.send_message(msg)
        print(f"HTML only test email sent successfully to {to_addr}")
        return True
    except Exception as e:
        print(f"Failed to send HTML only email: {e}")
        return False

if __name__ == "__main__":
    send_html_only_email()
```

</details>

You should see the test emails appear in the VaultBox web UI or via the API if everything is configured correctly.

## Future Development & Roadmap

- Refine and optimize the existing codebase
- Improve and modernize the web UI
- Explore or plan a migration to Go for enhanced performance and scalability

## License

This project is licensed under the MIT License.

## Team

VaultBox is a solo project. Please take it easy on the author!