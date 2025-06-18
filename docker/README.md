# VaultBox - Docker Image

A fully-featured secure mail receiver and testing tool with web interface, packaged as a Docker image for easy deployment. **Includes Redis** for message queuing - no external Redis required.

## 🚀 Quick Start

**⚠️ Prerequisites**: You must provide SSL certificates as base64-encoded environment variables. This container only accepts base64-encoded certificates for security and portability.

```bash
# Build the image
./build.sh

# Generate secure keys
SECRET_KEY=$(openssl rand -hex 32)
EMAIL_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Generate development SSL certificates (for testing only)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Convert certificates to base64 (required)
SSL_CERT_BASE64=$(base64 -w0 < cert.pem)
SSL_KEY_BASE64=$(base64 -w0 < key.pem)

# Run with required environment variables and base64 SSL certificates
docker run -d --name vaultbox-server \
  -e SECRET_KEY="$SECRET_KEY" \
  -e EMAIL_ENCRYPTION_KEY="$EMAIL_ENCRYPTION_KEY" \
  -e EMAIL_UI_USERS="admin:\$2b\$12\$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -p 8001:8001 -p 587:587 \
  vaultbox:latest
```

Access the web interface at http://localhost:8001

**Default credentials:**
- Username: `admin`
- Password: `admin123`
- TOTP Secret: `VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH`

⚠️ **Security Note**: The `SECRET_KEY` and `EMAIL_ENCRYPTION_KEY` environment variables are **required** for security. The image contains no sensitive defaults.

## 📋 Configuration

Configure the server using environment variables with `-e`:

### Essential Settings
```bash
docker run -d --name vaultbox-production \
  -e SECRET_KEY="your-super-secure-secret-key" \
  -e ENABLE_SWAGGER="false" \
  -e COOKIE_SECURE="true" \
  -e ACCESS_TOKEN_EXPIRE_MINUTES="60" \
  -p 8001:8001 -p 587:587 \
  vaultbox:latest
```

### All Available Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | **Required** | JWT signing key ⚠️ **Must be provided** |
| `EMAIL_ENCRYPTION_KEY` | **Required** | Email content encryption key ⚠️ **Must be provided** |
| `EMAIL_UI_USERS` | **Required** | User credentials: `username:hash:totp` (semicolon-separated for multiple users) ⚠️ **Must be provided** |
| `ENABLE_SWAGGER` | `true` | Enable API documentation at `/docs` |
| `ENABLE_UI` | `true` | Enable web interface |
| `COOKIE_SECURE` | `false` | Secure cookies (set `true` for HTTPS) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT token expiration time |
| `LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `SMTP_PORT` | `587` | SMTP server port |
| `WEB_PORT` | `8001` | Web interface port |
| `SMTP_HOST` | `0.0.0.0` | SMTP bind address |
| `WEB_HOST` | `0.0.0.0` | Web bind address |
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_URL` | `redis://localhost:6379` | Complete Redis URL |
| `REDIS_QUEUE` | `smtp_emails` | Redis queue name for email processing |
| `REDIS_PUBSUB_PREFIX` | `email_notify:` | Redis pub/sub prefix for notifications |
| `DATABASE_URL` | `sqlite:///./data/emails.db` | Database connection string |
| `SSL_CERT_BASE64` | **Required** | Base64-encoded SSL certificate ⚠️ **Must be provided** |
| `SSL_KEY_BASE64` | **Required** | Base64-encoded SSL private key ⚠️ **Must be provided** |

## 🌐 Usage Examples

### Development Environment
```bash
# Generate SSL certificates for development
openssl req -x509 -newkey rsa:4096 -keyout dev-key.pem -out dev-cert.pem -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Development/CN=localhost"
SSL_CERT_BASE64=$(base64 -w0 < dev-cert.pem)
SSL_KEY_BASE64=$(base64 -w0 < dev-key.pem)

docker run -d --name vaultbox-dev \
  -e SECRET_KEY="dev-secret-key" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:\$2b\$12\$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -e ENABLE_SWAGGER="true" \
  -e LOG_LEVEL="DEBUG" \
  -p 8001:8001 -p 587:587 \
  vaultbox:latest
```

### Production Environment
```bash
# Use production SSL certificates
SSL_CERT_BASE64=$(base64 -w0 < /path/to/your/cert.pem)
SSL_KEY_BASE64=$(base64 -w0 < /path/to/your/key.pem)

docker run -d --name vaultbox-prod \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:hash:totp" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -e ENABLE_SWAGGER="false" \
  -e COOKIE_SECURE="true" \
  -e ACCESS_TOKEN_EXPIRE_MINUTES="120" \
  -e LOG_LEVEL="WARNING" \
  -p 8001:8001 -p 587:587 \
  -v vaultbox-data:/app/data \
  -v vaultbox-logs:/app/logs \
  --restart unless-stopped \
  vaultbox:latest
```

### API-Only Mode (No Web UI)
```bash
docker run -d --name vaultbox-api \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:\$2b\$12\$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -e ENABLE_UI="false" \
  -e ENABLE_SWAGGER="true" \
  -p 8001:8001 -p 587:587 \
  vaultbox:latest
```

### Custom Ports
```bash
docker run -d --name vaultbox-custom \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:\$2b\$12\$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -e SMTP_PORT="2525" \
  -e WEB_PORT="8080" \
  -p 8080:8080 -p 2525:2525 \
  vaultbox:latest
```

## 🔐 SSL Certificate Configuration

**⚠️ IMPORTANT**: This Docker image requires SSL certificates as **base64-encoded environment variables only**. No file mounting is supported for maximum security and portability in cloud environments.

### Base64-Encoded Certificates (Required Method)

This is the only supported method for providing SSL certificates. It works perfectly with Docker, Kubernetes, and all cloud platforms without requiring volume mounts.

```bash
# Generate or obtain your SSL certificates
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=yourdomain.com"

# Convert certificates to base64 (single line, no wrapping)
SSL_CERT_BASE64=$(base64 -w0 < cert.pem)
SSL_KEY_BASE64=$(base64 -w0 < key.pem)

# Run with base64-encoded certificates
docker run -d --name vaultbox-server \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:hash:totp" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -p 8001:8001 -p 587:587 \
  vaultbox:latest
```

### Development Certificates (Testing Only)
```bash
# Generate self-signed certificates for development
openssl req -x509 -newkey rsa:4096 -keyout dev-key.pem -out dev-cert.pem -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Development/CN=localhost"

# Convert to base64
SSL_CERT_BASE64=$(base64 -w0 < dev-cert.pem)
SSL_KEY_BASE64=$(base64 -w0 < dev-key.pem)

# Run development container
docker run -d --name vaultbox-dev \
  -e SECRET_KEY="dev-secret-key" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:\$2b\$12\$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -e LOG_LEVEL="DEBUG" \
  -p 8001:8001 -p 587:587 \
  vaultbox:latest
```

### Production with Let's Encrypt Certificates
```bash
# Assuming you have Let's Encrypt certificates
SSL_CERT_BASE64=$(base64 -w0 < /etc/letsencrypt/live/yourdomain.com/fullchain.pem)
SSL_KEY_BASE64=$(base64 -w0 < /etc/letsencrypt/live/yourdomain.com/privkey.pem)

# Run production container
docker run -d --name vaultbox-prod \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:hash:totp" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -e ENABLE_SWAGGER="false" \
  -e COOKIE_SECURE="true" \
  -e LOG_LEVEL="WARNING" \
  -p 8001:8001 -p 587:587 \
  --restart unless-stopped \
  vaultbox:latest
```

### Kubernetes Deployment with Base64 Certificates
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: vaultbox-ssl-certs
type: Opaque
data:
  cert.pem: LS0tLS1CRUdJTi... # base64 encoded certificate
  key.pem: LS0tLS1CRUdJTi...  # base64 encoded private key
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vaultbox-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vaultbox-server
  template:
    metadata:
      labels:
        app: vaultbox-server
    spec:
      containers:
      - name: vaultbox-server
        image: vaultbox:latest
        ports:
        - containerPort: 8001
        - containerPort: 587
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: vaultbox-secrets
              key: secret-key
        - name: EMAIL_ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: vaultbox-secrets
              key: encryption-key
        - name: EMAIL_UI_USERS
          valueFrom:
            secretKeyRef:
              name: vaultbox-secrets
              key: ui-users
        - name: SSL_CERT_BASE64
          valueFrom:
            secretKeyRef:
              name: vaultbox-ssl-certs
              key: cert.pem
        - name: SSL_KEY_BASE64
          valueFrom:
            secretKeyRef:
              name: vaultbox-ssl-certs
              key: key.pem
```

**Security Notes for SSL:**
- Never use self-signed certificates in production
- Use proper CA-signed certificates for production deployments
- Base64 encoding allows secure certificate distribution without file dependencies
- Certificates are temporarily written to memory only during container startup
- No certificate files are stored permanently in the container
- Perfect for Kubernetes secrets and cloud deployments

## 🔧 Utility Commands

### Generate Secure Keys
```bash
# JWT secret key
openssl rand -hex 32

# Email encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# TOTP secret
python3 -c "import pyotp; print(pyotp.random_base32())"

# Password hash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())"
```

### Multiple Users
```bash
# Create user string: username:password_hash:totp_secret
USER1="admin:$(python3 -c 'import bcrypt; print(bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode())'):$(python3 -c 'import pyotp; print(pyotp.random_base32())')"
USER2="user2:$(python3 -c 'import bcrypt; print(bcrypt.hashpw(b"user2pass", bcrypt.gensalt()).decode())'):$(python3 -c 'import pyotp; print(pyotp.random_base32())')"

docker run -d --name vaultbox-multi-user \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="${USER1};${USER2}" \
  -p 8001:8001 -p 587:587 \
  vaultbox:latest
```

### Container Management
```bash
# View logs
docker logs vaultbox-server -f

# Execute shell in container
docker exec -it vaultbox-server /bin/bash

# Stop and remove
docker stop vaultbox-server && docker rm vaultbox-server
```

## 🔍 Accessing the Application

- **Web Interface**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs (if enabled)
- **API Endpoints**: http://localhost:8001/api/
- **SMTP Server**: localhost:587

## ⚠️ Security Notes

1. **Always change `SECRET_KEY` in production** - Generate with `openssl rand -hex 32`
2. **Generate unique `EMAIL_ENCRYPTION_KEY` for each deployment**
3. **Provide your own SSL certificates as base64** - The image contains no default certificates
4. **Use `COOKIE_SECURE=true` with HTTPS**
5. **Disable Swagger in production: `ENABLE_SWAGGER=false`**
6. **Create strong passwords and TOTP secrets**
7. **Use appropriate log levels for production**
8. **Never use self-signed certificates in production**
9. **Regularly renew SSL certificates before expiration**
10. **Base64-encoded certificates are perfect for cloud deployments and Kubernetes secrets**

## 🐳 Docker Compose Example

```yaml
version: '3.8'
services:
  vaultbox-server:
    image: vaultbox:latest
    ports:
      - "8001:8001"
      - "587:587"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - EMAIL_ENCRYPTION_KEY=${EMAIL_ENCRYPTION_KEY}
      - EMAIL_UI_USERS=${EMAIL_UI_USERS}
      - SSL_CERT_BASE64=${SSL_CERT_BASE64}
      - SSL_KEY_BASE64=${SSL_KEY_BASE64}
      - ENABLE_SWAGGER=false
      - COOKIE_SECURE=true
    volumes:
      - vaultbox_data:/app/data
      - vaultbox_logs:/app/logs
    restart: unless-stopped

volumes:
  vaultbox_data:
  vaultbox_logs:
```

## 🔧 Troubleshooting

### Check Configuration
```bash
# View environment variables
docker exec vaultbox-server printenv | grep -E "(SECRET_KEY|ENABLE_|LOG_LEVEL)"

# Test API access
curl -I http://localhost:8001/docs
curl -X GET http://localhost:8001/api/me
```

### View Logs
```bash
# Application logs
docker exec vaultbox-server cat logs/web.log
docker exec vaultbox-server cat logs/smtp.log

# Container logs
docker logs vaultbox-server
```
