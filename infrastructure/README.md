# Kstock Infrastructure Deployment on Google Cloud Platform (GCP) with Terraform

This directory contains production-ready Terraform code to deploy the **Kstock** infrastructure in the **Singapore (`asia-southeast1`)** region, enforcing a strict **3-Tier Network Isolation (Defense in Depth / Zero Trust)** architecture.

---

## 1. Architectural Overview (3-Tier Network Isolation)

- **Tier 1: Public Ingress Subnet (`10.10.10.0/24`)**:
  - Compute Instance: `kstock-ingress-vm` (Static Internal IP: `10.10.10.10`).
  - Assigned the **only public static IP** in the entire system.
  - Runs Nginx ModSecurity WAF / Reverse Proxy.
  - Firewall: Allows inbound HTTP (`80`) and HTTPS (`443`) from `0.0.0.0/0`. Only permitted to forward requests downstream to Tier 2.
- **Tier 2: Private Backend Subnet (`10.10.20.0/24`)**:
  - Compute Instance: `kstock-backend-vm` (Static Internal IP: `10.10.20.10`).
  - **No external public IP** (completely hidden from public Internet).
  - Runs `AuthenApp` (FastAPI:8000) and `InteractionApp` (Go:8080).
  - Firewall: Ingress strictly restricted to Tier 1 (Nginx). Outbound internet access via Cloud NAT (e.g. for Google OAuth, external APIs).
- **Tier 3: Restricted Data & Pipeline Subnet (`10.10.30.0/24`)**:
  - Compute Instance: `kstock-data-vm` (Static Internal IP: `10.10.30.10`).
  - **No external public IP**.
  - Attached independent **100GB Persistent SSD Disk** (`pd-balanced`), with automated daily snapshots at 02:00 UTC (09:00 AM Vietnam time, 7-day retention).
  - Runs: PostgreSQL (`5432`), ClickHouse (`8123`, `9000`), Redis (`6379`), Kafka (`9092`), Airflow, and Data Ingesters.
  - Firewall: Ingress strictly allowed only from Tier 2 (Backend) on database ports. Direct access from Nginx is explicitly dropped and logged. All public Internet inbound is dropped.
- **Secure Management (Zero Bastion Host)**:
  - SSH access is secured via **Google Cloud Identity-Aware Proxy (IAP)** (`gcloud compute ssh --tunnel-through-iap`) through Google netblock `35.235.240.0/20`. No open port 22 to the Internet.

---

## 2. Directory Layout

```text
infrastructure/
├── README.md                          # Deployment & verification guide
└── terraform/
    ├── main.tf                        # Root orchestration module
    ├── variables.tf                   # Input variable definitions
    ├── outputs.tf                     # Outputs (Public IP, Internal IPs, IAP SSH commands)
    ├── versions.tf                    # Terraform & GCP provider constraints
    ├── terraform.tfvars.example       # Example variable values
    └── modules/
        ├── vpc/                       # Custom VPC & 3 tiered subnets
        ├── nat/                       # Cloud Router & Cloud NAT Gateway (Secure Egress)
        ├── firewalls/                 # Zero-trust firewall matrix across tiers
        ├── iam/                       # Service Accounts & least privilege roles
        └── compute/                   # GCE VMs, Persistent SSD Disk, Static IPs
            └── scripts/
                ├── install_docker.sh  # Installs Docker Engine & Compose plugin
                └── mount_data_disk.sh # Formats ext4, mounts disk & prepares DB paths
```

---

## 3. Deployment Steps

### Step 1: GCP Authentication & API Enablement
Ensure `gcloud` CLI is installed and authenticated:
```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your target project
gcloud config set project YOUR_PROJECT_ID

# Enable required Google Cloud APIs
gcloud services enable compute.googleapis.com iap.googleapis.com
```

### Step 2: Configure `terraform.tfvars`
Navigate to the terraform directory and copy the template:
```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
```
Edit `terraform.tfvars` and set your `project_id = "YOUR_ACTUAL_GCP_PROJECT_ID"`.

### Step 3: Initialize and Validate
```bash
# Initialize Terraform and download providers
terraform init

# Validate syntax and configuration
terraform validate

# Review the execution plan
terraform plan
```

### Step 4: Apply Configuration
```bash
terraform apply
```
Type `yes` when prompted. When completed, Terraform outputs:
- **`nginx_public_ip`**: Public IP to point your domain DNS A-record to.
- **`data_internal_ip`**: `10.10.30.10` (used as database host in Backend `.env`).
- **`backend_internal_ip`**: `10.10.20.10` (used in Nginx upstream configuration).
- **`ssh_commands`**: 3 copy-pasteable IAP SSH commands to connect to each VM.

---

## 4. Application Deployment Workflow

### 4.1. Tier 3: Data & Pipeline VM
Connect via IAP SSH:
```bash
gcloud compute ssh kstock-data-vm --zone=asia-southeast1-b --tunnel-through-iap
```
- The persistent disk is automatically mounted at `/mnt/disks/kstock-data` (symlinked at `/opt/kstock/data`).
- Launch databases and data pipelines via Docker Compose:
```bash
cd /opt/kstock
# Place docker-compose.yml here with volume mounts mapped to /mnt/disks/kstock-data
docker compose up -d
```

### 4.2. Tier 2: Backend Applications VM
Connect via IAP SSH:
```bash
gcloud compute ssh kstock-backend-vm --zone=asia-southeast1-b --tunnel-through-iap
```
Configure environment variables in `.env` for `AuthenApp` and `InteractionApp`:
- `POSTGRES_HOST=10.10.30.10`
- `REDIS_HOST=10.10.30.10`
- `CLICKHOUSE_HOST=10.10.30.10`
Launch services:
```bash
docker compose up -d
```

### 4.3. Tier 1: Nginx Ingress VM
Connect via IAP SSH:
```bash
gcloud compute ssh kstock-ingress-vm --zone=asia-southeast1-b --tunnel-through-iap
```
Configure Nginx reverse proxy upstream to point to the Backend internal IP:
```nginx
upstream backend_auth {
    server 10.10.20.10:8000;
}

upstream backend_api {
    server 10.10.20.10:8080;
}
```
Launch Nginx ModSecurity WAF container:
```bash
docker compose up -d
```

---

## 5. Security & Isolation Verification Tests

Run these 4 verification checks after deployment to validate network tier isolation:

1. **Test Nginx -> Backend (Expected: SUCCESS)**:
   - From `kstock-ingress-vm`: `curl http://10.10.20.10:8000` -> Receives response from FastAPI.
2. **Test Nginx -> Database (Expected: BLOCKED & DROPPED)**:
   - From `kstock-ingress-vm`: `nc -zv 10.10.30.10 5432` -> **Timeout / Connection Dropped** (Firewall explicitly drops direct Ingress-to-Data traffic).
3. **Test Backend -> Database (Expected: SUCCESS)**:
   - From `kstock-backend-vm`: `nc -zv 10.10.30.10 5432` or `curl http://10.10.30.10:8123/ping` -> Returns `Ok.` from ClickHouse.
4. **Test Public Internet -> Backend/DB (Expected: UNREACHABLE)**:
   - From an external machine: Any attempt to connect directly to private IPs `10.10.20.10` or `10.10.30.10` is non-routable (no external IP exists).
