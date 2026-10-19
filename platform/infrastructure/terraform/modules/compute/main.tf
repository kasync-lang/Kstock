# ==============================================================================
# 1. STATIC IPs (PUBLIC & INTERNAL)
# ==============================================================================

# Static External Public IP for Nginx Ingress
resource "google_compute_address" "nginx_public_ip" {
  name         = "kstock-nginx-public-ip"
  region       = var.region
  address_type = "EXTERNAL"
  description  = "Sole public IP address of the system, assigned to Nginx Ingress WAF"
}

# Static Internal IP for Ingress VM
resource "google_compute_address" "ingress_internal_ip" {
  name         = "kstock-ingress-internal-ip"
  subnetwork   = var.subnet_public_ingress_id
  address_type = "INTERNAL"
  address      = var.ingress_internal_ip
  region       = var.region
  description  = "Static private IP for Nginx Ingress VM"
}

# Static Internal IP for Backend VM
resource "google_compute_address" "backend_internal_ip" {
  name         = "kstock-backend-internal-ip"
  subnetwork   = var.subnet_backend_app_id
  address_type = "INTERNAL"
  address      = var.backend_internal_ip
  region       = var.region
  description  = "Static private IP for Backend Applications VM"
}

# Static Internal IP for Data & Pipeline VM
resource "google_compute_address" "data_internal_ip" {
  name         = "kstock-data-internal-ip"
  subnetwork   = var.subnet_data_pipeline_id
  address_type = "INTERNAL"
  address      = var.data_internal_ip
  region       = var.region
  description  = "Static private IP for Database and Pipeline VM"
}

# ==============================================================================
# 2. PERSISTENT DISK FOR DATABASE STORAGE & AUTOMATED DAILY SNAPSHOT
# ==============================================================================

# Automated daily snapshot schedule policy (02:00 UTC ~ 09:00 AM VN, 7-day retention)
resource "google_compute_resource_policy" "daily_snapshot_policy" {
  name   = "kstock-db-daily-snapshot-policy"
  region = var.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "02:00"
      }
    }
    retention_policy {
      max_retention_days    = 7
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }
  }
}

# Dedicated persistent SSD disk for databases (PostgreSQL, ClickHouse, Redis)
resource "google_compute_disk" "data_disk" {
  name = "kstock-data-disk"
  type = "pd-balanced"
  zone = var.zone
  size = var.data_disk_size_gb

  description = "Independent Persistent Disk storing all PostgreSQL, ClickHouse, and Redis data"
}

# Attach snapshot policy to the persistent disk
resource "google_compute_disk_resource_policy_attachment" "attachment" {
  name = google_compute_resource_policy.daily_snapshot_policy.name
  disk = google_compute_disk.data_disk.name
  zone = var.zone
}

# ==============================================================================
# 3. COMPUTE INSTANCES (TIERED VIRTUAL MACHINES)
# ==============================================================================

# --- VM 1: Ingress (Nginx ModSecurity WAF) ---
resource "google_compute_instance" "ingress_vm" {
  name         = "kstock-ingress-vm"
  machine_type = var.ingress_machine_type
  zone         = var.zone

  tags = ["ingress-proxy"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet_public_ingress_id
    network_ip = google_compute_address.ingress_internal_ip.address

    # Assign public IP for inbound Internet users
    access_config {
      nat_ip = google_compute_address.nginx_public_ip.address
    }
  }

  metadata_startup_script = file("${path.module}/scripts/install_docker.sh")

  service_account {
    email  = var.sa_ingress_email
    scopes = ["cloud-platform"]
  }

  description = "Tier 1: Nginx Ingress WAF Reverse Proxy"
}

# --- VM 2: Backend Apps (AuthenApp & InteractionApp) ---
resource "google_compute_instance" "backend_vm" {
  name         = "kstock-backend-vm"
  machine_type = var.backend_machine_type
  zone         = var.zone

  tags = ["backend-app"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet_backend_app_id
    network_ip = google_compute_address.backend_internal_ip.address
    # NO access_config block -> STRICTLY NO PUBLIC IP
  }

  metadata_startup_script = file("${path.module}/scripts/install_docker.sh")

  service_account {
    email  = var.sa_backend_email
    scopes = ["cloud-platform"]
  }

  description = "Tier 2: Backend Application VM (Private Only)"
}

# --- VM 3: Data & Data Pipeline (Postgres, ClickHouse, Redis, Kafka, Airflow) ---
resource "google_compute_instance" "data_vm" {
  name         = "kstock-data-vm"
  machine_type = var.data_machine_type
  zone         = var.zone

  tags = ["data-db", "data-pipeline"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 40
      type  = "pd-standard"
    }
  }

  # Attach independent persistent data disk
  attached_disk {
    source      = google_compute_disk.data_disk.id
    device_name = "kstock-data-disk"
    mode        = "READ_WRITE"
  }

  network_interface {
    subnetwork = var.subnet_data_pipeline_id
    network_ip = google_compute_address.data_internal_ip.address
    # NO access_config block -> STRICTLY NO PUBLIC IP
  }

  # Startup script auto-formats disk, mounts to /mnt/disks/kstock-data, and installs Docker
  metadata_startup_script = file("${path.module}/scripts/mount_data_disk.sh")

  service_account {
    email  = var.sa_data_email
    scopes = ["cloud-platform"]
  }

  description = "Tier 3: Database and Data Pipeline VM (Restricted Private Only)"
}
