# Remote Deployment Guide — Hostinger VPS

## Overview
This guide deploys the Higgsfield MCP server on a Hostinger VPS, accessible via `https://mcp.qalalabs.com/mcp`.

## Prerequisites
- Hostinger VPS plan (Ubuntu 22.04 or 24.04)
- Domain `qalalabs.com` managed through Hostinger DNS
- SSH access to your VPS

---

## Step 1: Create Subdomain

1. Go to **Hostinger Dashboard** → **Domains** → `qalalabs.com`
2. Click **DNS / Name Servers**
3. Add an **A Record**:
   - **Type**: A
   - **Name**: `mcp`
   - **Points to**: Your VPS IP address
   - **TTL**: 14400
4. Save and wait ~15 min for DNS propagation

---

## Step 2: SSH into Your VPS

```bash
ssh root@YOUR_VPS_IP
```

---

## Step 3: Install Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Docker + Docker Compose
apt install -y docker.io docker-compose-plugin
systemctl enable docker
systemctl start docker

# Install Nginx
apt install -y nginx
systemctl enable nginx
systemctl start nginx

# Install Certbot for SSL
apt install -y certbot python3-certbot-nginx
```

---

## Step 4: Deploy the MCP Server

### Option A: Clone from GitHub (Recommended)

```bash
cd /opt
git clone https://github.com/QalaLabs/claude-higgsfield-mcp.git
cd claude-higgsfield-mcp

# Create .env.server with your credentials
cp .env.server.example .env.server
nano .env.server
```

Edit `.env.server` with your actual values:
```
HF_API_KEY=35a026fe-d0e6-4b05-aa1a-f9a89840eb18
HF_SECRET=7e34bf35f41b0c34d99ff48a8771e81ffc25c4acb4ed65dce25924c388fac1c5
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_PATH=/mcp
MCP_API_KEY=your-random-secret-key-here
```

Generate a random `MCP_API_KEY`:
```bash
openssl rand -hex 32
```

### Option B: Upload Files Manually

If you don't want to clone from GitHub, use `scp` to upload:
```bash
scp -r claude-higgsfield-mcp root@YOUR_VPS_IP:/opt/
```

---

## Step 5: Start the Docker Container

```bash
cd /opt/claude-higgsfield-mcp
docker compose up -d --build
```

Verify it's running:
```bash
docker ps
# You should see higgsfield-mcp running on port 8000

curl http://127.0.0.1:8000/health
# Should return a response
```

---

## Step 6: Configure Nginx Reverse Proxy

```bash
# Copy the nginx config
cp nginx.conf /etc/nginx/sites-available/mcp.qalalabs.com
ln -s /etc/nginx/sites-available/mcp.qalalabs.com /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # Remove default site if present

# Test nginx config
nginx -t

# Reload nginx
systemctl reload nginx
```

---

## Step 7: Get SSL Certificate

```bash
certbot --nginx -d mcp.qalalabs.com
```

Follow the prompts. This will automatically update your nginx config with SSL.

---

## Step 8: Test the Remote Endpoint

```bash
curl https://mcp.qalalabs.com/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-random-secret-key-here" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

You should get a JSON response from the MCP server.

---

## Step 9: Configure Claude Desktop (or Claude.ai)

### For Claude Desktop:
Edit your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "higgsfield": {
      "url": "https://mcp.qalalabs.com/mcp",
      "headers": {
        "X-API-Key": "your-random-secret-key-here"
      }
    }
  }
}
```

### For Claude.ai (Web):
Claude.ai currently only supports cloud connectors, not custom remote MCP servers. You'll need to use **Claude Desktop** for custom MCP connections.

---

## Step 10: Set Up Auto-Updates

```bash
# Create update script
cat > /opt/claude-higgsfield-mcp/update.sh << 'EOF'
#!/bin/bash
cd /opt/claude-higgsfield-mcp
git pull
docker compose up -d --build
EOF

chmod +x /opt/claude-higgsfield-mcp/update.sh

# Add to crontab (update daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/claude-higgsfield-mcp/update.sh >> /var/log/mcp-update.log 2>&1") | crontab -
```

---

## Monitoring

```bash
# View logs
docker logs -f higgsfield-mcp

# Check server status
curl https://mcp.qalalabs.com/mcp

# Check system resources
htop
```

---

## Troubleshooting

### Container won't start
```bash
docker logs higgsfield-mcp
```

### Nginx returns 502
```bash
# Make sure the container is running
docker ps
# Make sure nginx can reach port 8000
curl http://127.0.0.1:8000/health
```

### SSL certificate errors
```bash
certbot renew --dry-run
```

### DNS not propagating
```bash
# Check from your machine
nslookup mcp.qalalabs.com
# Should return your VPS IP
```

---

## Security Notes

1. **Never commit `.env.server`** — it's already in `.gitignore`
2. **Use a strong `MCP_API_KEY`** — generate with `openssl rand -hex 32`
3. **Keep your VPS updated** — `apt update && apt upgrade -y` weekly
4. **Set up a firewall** (optional but recommended):
   ```bash
   ufw allow 22/tcp
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```
