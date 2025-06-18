# VaultBox

A fully-featured SMTP server with web interface for receiving and managing emails. Built with Python, FastAPI, and Redis.

## ✨ Features

- 📧 SMTP server with STARTTLS support (port 587)
- 🌐 Web interface for email management
- 🔒 JWT authentication with TOTP 2FA
- 📊 REST API with Swagger documentation
- 🔄 Real-time email notifications via WebSocket
- 💾 SQLite database for email storage
- 🚀 Redis for message queuing
- 🐳 Docker support with embedded Redis

## 🚀 Quick Start

### Local Development

1. **Copy environment configuration:**
   ```bash
   cp .env.example .env
   ```

2. **Generate SSL certificates:**
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
     -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
   ```

3. **Convert certificates to base64 and update .env:**
   ```bash
   SSL_CERT_BASE64=$(base64 -w0 < cert.pem)
   SSL_KEY_BASE64=$(base64 -w0 < key.pem)
   echo "SSL_CERT_BASE64=$SSL_CERT_BASE64" >> .env
   echo "SSL_KEY_BASE64=$SSL_KEY_BASE64" >> .env
   ```

4. **Generate secure keys and update .env:**
   ```bash
   SECRET_KEY=$(openssl rand -hex 32)
   EMAIL_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   echo "SECRET_KEY=$SECRET_KEY" >> .env
   echo "EMAIL_ENCRYPTION_KEY=$EMAIL_ENCRYPTION_KEY" >> .env
   ```

5. **Start the SMTP server (automatically detects Redis):**
   ```bash
   ./run.sh start
   ```
   
   The script will automatically:
   - ✅ **Use local Redis** if installed (`brew install redis`)
   - ⚠️  **Use Docker Redis** if Redis not found but Docker available
   - ❌ **Show installation options** if neither available

### Redis Options

**Option A: Install Redis locally (recommended for development):**
```bash
# Install Redis
brew install redis

# Start server (Redis will be auto-detected)
./run.sh start
```

**Option B: Use Docker Redis (automatic fallback):**
```bash
# Just start - Docker Redis will be used automatically if local Redis not found
./run.sh start
```

**Option C: Use full Docker container (includes everything):**
Skip to Docker Deployment section - it includes embedded Redis and requires no local setup.

### Docker Deployment

See [docker/README.md](docker/README.md) for complete Docker deployment instructions.

**Quick Docker run:**
```bash
cd docker
./build.sh

# Generate certificates and keys
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
SSL_CERT_BASE64=$(base64 -w0 < cert.pem)
SSL_KEY_BASE64=$(base64 -w0 < key.pem)

# Run container (includes embedded Redis)
docker run -d --name smtp-server \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e EMAIL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e EMAIL_UI_USERS="admin:\$2b\$12\$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH" \
  -e SSL_CERT_BASE64="$SSL_CERT_BASE64" \
  -e SSL_KEY_BASE64="$SSL_KEY_BASE64" \
  -p 8001:8001 -p 587:587 \
  smtp-email-server:latest
```

## 🔐 Configuration

All configuration is done via environment variables. See `.env.example` for all available options.

### Required Variables
- `SECRET_KEY` - JWT signing key
- `EMAIL_ENCRYPTION_KEY` - Email content encryption key  
- `EMAIL_UI_USERS` - User credentials (username:hash:totp)
- `SSL_CERT_BASE64` - Base64-encoded SSL certificate
- `SSL_KEY_BASE64` - Base64-encoded SSL private key

### Default Credentials
- **Username:** `admin`
- **Password:** `admin123`
- **TOTP Secret:** `VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH`

⚠️ **Change these in production!**

## 🌐 Access URLs

- **Web Interface:** http://localhost:8001
- **API Documentation:** http://localhost:8001/docs
- **SMTP Server:** localhost:587

## 📋 Commands

```bash
./run.sh start    # Start all services
./run.sh stop     # Stop all services  
./run.sh status   # Check service status
./run.sh logs     # View recent logs
./run.sh test     # Send test email
./run.sh totp     # Generate TOTP code
```

## 🔧 Development

### Requirements
- Python 3.8+
- Redis server
- OpenSSL

### Installation
```bash
pip install -r requirements.txt
```

### SSL Certificates
This application **only** accepts base64-encoded SSL certificates via environment variables. This ensures:
- ✅ Consistent deployment across Docker/Kubernetes/cloud
- ✅ No file mounting dependencies
- ✅ Perfect for CI/CD and cloud deployments
- ✅ Secure secret management

## 🐳 Docker Features

- **Self-contained:** Redis embedded in container
- **Cloud-ready:** Works with Kubernetes, GCP, AWS, Azure
- **Secure:** No default certificates, requires user-provided SSL
- **Professional:** Environment variable configuration like major Docker images

## 📚 API Documentation

Access the interactive API documentation at `/docs` when the server is running.

## 🧪 Testing

Send a test email:
```bash
./run.sh test
```

Or manually:
```bash
python testing/send_test_email.py
```

## 🔒 Security Notes

1. **Always change default credentials in production**
2. **Use strong `SECRET_KEY` and `EMAIL_ENCRYPTION_KEY`**
3. **Use proper CA-signed certificates for production**
4. **Set `COOKIE_SECURE=true` with HTTPS**
5. **Disable Swagger in production: `ENABLE_SWAGGER=false`**

## 📄 License

This project is licensed under the MIT License.
