#!/usr/bin/env bash
set -euo pipefail

echo "===== [1/4] Running Docker Install ====="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker

echo "===== [2/4] Formatting & Mounting Persistent Data Disk ====="
DEVICE_PATH="/dev/disk/by-id/google-kstock-data-disk"
MOUNT_POINT="/mnt/disks/kstock-data"

mkdir -p "$MOUNT_POINT"

# Wait for the disk device to become available
while [ ! -b "$DEVICE_PATH" ]; do
  echo "Waiting for disk device $DEVICE_PATH to become available..."
  sleep 2
done

# Check if disk is formatted, if not format with ext4
if ! blkid "$DEVICE_PATH" > /dev/null; then
  echo "Formatting $DEVICE_PATH with ext4 filesystem..."
  mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard "$DEVICE_PATH"
fi

# Mount disk
if ! mountpoint -q "$MOUNT_POINT"; then
  mount -o discard,defaults "$DEVICE_PATH" "$MOUNT_POINT"
fi

# Add to /etc/fstab for auto-mount across reboots
UUID=$(blkid -s UUID -o value "$DEVICE_PATH")
if ! grep -q "$UUID" /etc/fstab; then
  echo "UUID=$UUID $MOUNT_POINT ext4 discard,defaults,nofail 0 2" >> /etc/fstab
fi

echo "===== [3/4] Preparing Database & Pipeline Directories ====="
mkdir -p "$MOUNT_POINT/postgres"
mkdir -p "$MOUNT_POINT/clickhouse"
mkdir -p "$MOUNT_POINT/redis"
mkdir -p "$MOUNT_POINT/kafka"
chmod -R 777 "$MOUNT_POINT"

# Create symbolic link for convenience
mkdir -p /opt/kstock
ln -sfn "$MOUNT_POINT" /opt/kstock/data

echo "===== [4/4] Data VM Initialization Completed Successfully ====="

