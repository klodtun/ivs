#!/bin/bash
# ============================================
# IVS - Internal Vibe Server Setup Script
# ============================================
set -e

echo "============================================"
echo "  IVS - Internal Vibe Server Setup"
echo "  Enterprise Gateway for Vibe Code Apps"
echo "============================================"
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo "Warning: Unsupported OS. Proceeding anyway..."
    OS="unknown"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "[!] Docker not found. Installing..."
    if [ "$OS" = "linux" ]; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker "$USER"
        rm get-docker.sh
        echo "[+] Docker installed. You may need to log out and back in."
    else
        echo "[!] Please install Docker Desktop from https://docker.com"
        exit 1
    fi
else
    echo "[+] Docker found: $(docker --version)"
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "[!] Docker Compose not found."
    echo "    Please install Docker Compose v2."
    exit 1
else
    echo "[+] Docker Compose found: $(docker compose version --short)"
fi

# Get server IP
DEFAULT_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "192.168.1.100")
read -p "Server IP address [$DEFAULT_IP]: " SERVER_IP
SERVER_IP=${SERVER_IP:-$DEFAULT_IP}

# Get domain suffix
read -p "Domain suffix [vibe.local]: " DOMAIN_SUFFIX
DOMAIN_SUFFIX=${DOMAIN_SUFFIX:-vibe.local}

# Get admin password
read -s -p "Admin password [admin123]: " ADMIN_PASSWORD
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
echo ""

# Generate secrets
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "ivs-$(date +%s)-secret-key")
VAULT_KEY=$(openssl rand -hex 32 2>/dev/null || echo "ivs-$(date +%s)-vault-key")

# Create .env file
cd "$(dirname "$0")/.."

cat > .env << EOF
SECRET_KEY=${SECRET_KEY}
VAULT_KEY=${VAULT_KEY}
DOMAIN_SUFFIX=${DOMAIN_SUFFIX}
SERVER_IP=${SERVER_IP}
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF

echo "[+] Configuration saved to .env"

# Create data directories
mkdir -p data deployed_apps uploads
echo "[+] Data directories created"

# Update CoreDNS hosts
cat > coredns/hosts << EOF
# IVS Auto-generated DNS hosts
${SERVER_IP} ${DOMAIN_SUFFIX}
${SERVER_IP} api.${DOMAIN_SUFFIX}
${SERVER_IP} git.${DOMAIN_SUFFIX}
EOF
echo "[+] DNS hosts configured"

# Build and start
echo ""
echo "[*] Building and starting IVS services..."
docker compose build
docker compose up -d

echo ""
echo "============================================"
echo "  IVS Setup Complete!"
echo "============================================"
echo ""
echo "  Dashboard:  http://${SERVER_IP}:3000"
echo "  API:        http://${SERVER_IP}:8000"
echo "  Gitea:      http://${SERVER_IP}:3001"
echo ""
echo "  Local DNS:  http://${DOMAIN_SUFFIX}"
echo "  (Set your PC DNS to ${SERVER_IP})"
echo ""
echo "  Login:      admin / ${ADMIN_PASSWORD}"
echo ""
echo "============================================"
