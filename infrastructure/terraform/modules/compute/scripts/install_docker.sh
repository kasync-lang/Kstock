#!/usr/bin/env bash
set -euo pipefail

echo "===== [1/3] Updating System Packages ====="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release

echo "===== [2/3] Installing Docker Engine & Compose Plugin ====="
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "===== [3/3] Enabling and Starting Docker ====="
systemctl enable docker
systemctl start docker

# Create deployment directories for Kstock application
mkdir -p /opt/kstock /opt/kstock/logs

echo "===== Docker installation completed successfully ====="

