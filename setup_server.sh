#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Ananta — One-command server setup for DigitalOcean Ubuntu 22.04
# Run as root on a fresh droplet:
#   curl -sO https://raw.githubusercontent.com/YOUR/dokan/main/setup_server.sh
#   bash setup_server.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

REPO_URL="https://github.com/anjani-sharma/dokan.git"
APP_DIR="/opt/ananta"
DOMAIN=""   # leave blank to skip SSL (use IP address)

echo "╔══════════════════════════════════════════╗"
echo "║     Ananta Shop App — Server Setup       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. System packages
echo "▶ Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    docker.io docker-compose-v2 \
    git curl certbot nginx-light \
    ufw fail2ban

# 2. Enable firewall
echo "▶ Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 3. Clone repo
echo "▶ Cloning application..."
rm -rf "$APP_DIR"
git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"

# 4. Create .env from example
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "┌─────────────────────────────────────────┐"
    echo "│  ACTION REQUIRED: edit your .env file   │"
    echo "│  nano /opt/ananta/.env                  │"
    echo "│  Then re-run: bash deploy.sh            │"
    echo "└─────────────────────────────────────────┘"
    echo ""
fi

# 5. SSL certificate (Let's Encrypt) — only if domain provided
if [ -n "$DOMAIN" ]; then
    echo "▶ Getting SSL certificate for $DOMAIN..."
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos -m admin@"$DOMAIN"
    mkdir -p "$APP_DIR/nginx/certs"
    cp /etc/letsencrypt/live/"$DOMAIN"/fullchain.pem "$APP_DIR/nginx/certs/"
    cp /etc/letsencrypt/live/"$DOMAIN"/privkey.pem   "$APP_DIR/nginx/certs/"

    # Auto-renew SSL
    echo "0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/*.pem $APP_DIR/nginx/certs/ && cd $APP_DIR && docker compose restart nginx" \
        | crontab -
else
    echo "▶ No domain set — using self-signed cert for now..."
    mkdir -p "$APP_DIR/nginx/certs"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$APP_DIR/nginx/certs/privkey.pem" \
        -out    "$APP_DIR/nginx/certs/fullchain.pem" \
        -subj "/CN=ananta-local"
fi

# 6. Auto-start on reboot
echo "▶ Setting up auto-start..."
cat > /etc/systemd/system/ananta.service << EOF
[Unit]
Description=Ananta Shop App
After=docker.service
Requires=docker.service

[Service]
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ananta

echo ""
echo "✅ Server setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit your config:  nano /opt/ananta/.env"
echo "  2. Deploy the app:    bash /opt/ananta/deploy.sh"
echo ""
