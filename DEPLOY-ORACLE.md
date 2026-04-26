# CineAlert — Oracle Cloud Free Tier Deployment

Oracle Cloud Always Free Tier provides a permanently free ARM VM that runs 24/7. No code changes needed — the existing Docker setup works as-is on ARM.

## What You Get (Free Forever)

- **VM.Standard.A1.Flex** (ARM) — 1 OCPU, 6 GB RAM
- 200 GB block storage
- Always-on, no sleep, no expiry
- Credit card required for signup verification only (authorized $1, then released)

## Step 1: Sign Up

1. Go to https://signup.oraclecloud.com/
2. Provide email, verify, add card
3. Select home region (e.g., **Canada Southeast (Toronto)**)

## Step 2: Create a VM Instance

1. Go to **Compute > Instances > Create Instance**
2. Shape: **VM.Standard.A1.Flex** (Ampere ARM)
3. Image: **Oracle Linux 8**
4. Resources: **1 OCPU / 6 GB RAM**
5. Under **Add SSH keys**: download the private key (or paste your own public key)
6. Click **Create** and note the **public IP address**

## Step 3: SSH In and Install Docker

```bash
ssh -i <your-private-key> opc@<instance-public-ip>

# Update system
sudo dnf update -y

# Install Docker
sudo dnf install -y dnf-utils zip unzip
sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker opc

# Log out and back in for group change
exit
ssh -i <your-private-key> opc@<instance-public-ip>

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Git
sudo dnf install -y git
```

## Step 4: Clone and Configure

```bash
cd ~
git clone https://github.com/rahulkahani/cinealert.git
cd cinealert
```

Edit `docker-compose.yml` with your credentials:

```bash
nano docker-compose.yml
```

Set these environment variables:
- `EMAIL` — your Gmail address
- `PASSWORD` — your Gmail **app password** (not your regular password; generate at https://myaccount.google.com/apppasswords)
- `PHONE` — e.g., `5551234567:Rogers` (comma-separated for multiple: `5551234567:Rogers,5559876543:Bell`)

## Step 5: Build and Run

```bash
make build
make run
```

Or without Make:

```bash
docker compose build
docker compose up -d
```

## Step 6: Verify

```bash
# Container should show as running
docker ps

# Watch live logs
docker compose logs -f

# Check app output
cat logs/main.log

# Confirm cron schedule
docker exec cinealert crontab -l
```

## Why No Code Changes Are Needed

- `python:3.10-slim` supports ARM64 natively (Docker auto-pulls the right variant)
- All dependencies (`requests`, `beautifulsoup4`) are pure Python
- No firewall changes needed — app only makes outbound HTTPS requests
- Cron runs inside the container every 15 minutes

## Verification Checklist

- [ ] Container shows as running in `docker ps`
- [ ] `logs/main.log` shows successful scrape of both movie pages
- [ ] SMS delivery reaches your phone (test with a movie that has existing showtimes)
- [ ] Wait 15 minutes and confirm cron triggers another run

## Maintenance

```bash
# View logs
make logs

# Stop
make stop

# Update code
cd ~/cinealert && git pull && make build && make run

# Full reset
make purge && make build && make run
```
