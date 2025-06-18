#!/bin/bash

# Simple script to build the Docker image

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "- Building Vaultbox Docker Image"
echo "==========================================="
echo "Project root: $PROJECT_ROOT"
echo ""

# Build the image
echo "Building Docker image..."
cd "$SCRIPT_DIR"

docker build -t vaultbox:latest \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  -f Dockerfile \
  "$PROJECT_ROOT"

echo ""
echo "✅ Docker image built successfully!"
echo ""
echo "⚠️  IMPORTANT: SSL certificates are required as base64-encoded environment variables!"
echo "   This image does NOT include SSL certificates and ONLY accepts base64-encoded certificates."
echo "   No file mounting is supported for maximum security and cloud compatibility."
echo ""
echo "📋 Quick Start:"
echo "  # Generate SSL certificates and convert to base64"
echo "  openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \\"
echo "    -subj \"/C=US/ST=State/L=City/O=Organization/CN=localhost\""
echo "  SSL_CERT_BASE64=\$(base64 -w0 < cert.pem)"
echo "  SSL_KEY_BASE64=\$(base64 -w0 < key.pem)"
echo ""
echo "  # Run with base64-encoded certificates"
echo "  docker run -d --name my-smtp-server \\"
echo "    -e SECRET_KEY=\"\$(openssl rand -hex 32)\" \\"
echo "    -e EMAIL_ENCRYPTION_KEY=\"\$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')\" \\"
echo "    -e EMAIL_UI_USERS=\"admin:hash:totp\" \\"
echo "    -e SSL_CERT_BASE64=\"\$SSL_CERT_BASE64\" \\"
echo "    -e SSL_KEY_BASE64=\"\$SSL_KEY_BASE64\" \\"
echo "    -p 8001:8001 -p 587:587 \\"
echo "    smtp-email-server:latest"
echo ""
echo "📖 For more examples and production setup, see: README.md"
