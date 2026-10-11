# ==============================================================================
# 1. TIER 1: Allow public internet inbound to Nginx Ingress WAF (Ports 80, 443)
# ==============================================================================
resource "google_compute_firewall" "allow_internet_to_ingress" {
  name        = "${var.network_name}-allow-internet-to-ingress"
  network     = var.network_name
  description = "Allow inbound HTTP/HTTPS traffic from public Internet to Nginx Ingress only"

  direction = "INGRESS"
  priority  = 1000

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ingress-proxy"]

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
}

# ==============================================================================
# 2. TIER 1 -> TIER 2: Allow Nginx to connect to Backend Apps (Ports 8000, 8080)
# ==============================================================================
resource "google_compute_firewall" "allow_ingress_to_backend" {
  name        = "${var.network_name}-allow-ingress-to-backend"
  network     = var.network_name
  description = "Allow traffic from Ingress Subnet to Backend Apps (AuthenApp, InteractionApp)"

  direction = "INGRESS"
  priority  = 1000

  # Only accept traffic originating from Ingress Subnet CIDR
  source_ranges = [var.subnet_public_cidr]
  target_tags   = ["backend-app"]

  allow {
    protocol = "tcp"
    ports    = ["8000", "8080"]
  }
}

# ==============================================================================
# 3. TIER 2 -> TIER 3: Allow Backend to connect to Databases (Ports 5432, 6379, 8123, 9000)
# ==============================================================================
resource "google_compute_firewall" "allow_backend_to_db" {
  name        = "${var.network_name}-allow-backend-to-db"
  network     = var.network_name
  description = "Allow traffic from Backend Subnet to Database ports (PostgreSQL, ClickHouse, Redis)"

  direction = "INGRESS"
  priority  = 1000

  # Only accept traffic originating from Backend Subnet CIDR
  source_ranges = [var.subnet_backend_cidr]
  target_tags   = ["data-db"]

  allow {
    protocol = "tcp"
    ports = [
      "5432", # PostgreSQL
      "6379", # Redis
      "8123", # ClickHouse HTTP API
      "9000"  # ClickHouse Native Client
    ]
  }
}

# ==============================================================================
# 4. TIER 3 INTERNAL: Allow Data Pipeline & Databases internal communication
# ==============================================================================
resource "google_compute_firewall" "allow_pipeline_internal" {
  name        = "${var.network_name}-allow-pipeline-internal"
  network     = var.network_name
  description = "Allow internal traffic within Data & Pipeline subnet for Kafka, Airflow, and DBs"

  direction = "INGRESS"
  priority  = 1000

  # Only accept traffic within Data & Pipeline Subnet CIDR
  source_ranges = [var.subnet_data_cidr]
  target_tags   = ["data-db", "data-pipeline"]

  allow {
    protocol = "tcp"
    ports = [
      "5432",  # PostgreSQL
      "6379",  # Redis
      "8123",  # ClickHouse HTTP
      "9000",  # ClickHouse Native
      "9092",  # Kafka Internal
      "29092", # Kafka Broker
      "8793",  # Airflow Worker Log server
      "8080"   # Airflow Webserver (internal)
    ]
  }
}

# ==============================================================================
# 5. SECURE OPS: Allow Google Cloud Identity-Aware Proxy (IAP) SSH access
# ==============================================================================
resource "google_compute_firewall" "allow_iap_ssh" {
  name        = "${var.network_name}-allow-iap-ssh"
  network     = var.network_name
  description = "Allow secure SSH tunneling via Google Cloud IAP without public IP"

  direction = "INGRESS"
  priority  = 900

  # Official Google Cloud IAP TCP Forwarding netblock
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["ingress-proxy", "backend-app", "data-db", "data-pipeline"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# ==============================================================================
# 6. EXPLICIT SECURITY: Deny and log any direct Ingress to Data Tier access attempt
# ==============================================================================
resource "google_compute_firewall" "deny_ingress_to_data" {
  name        = "${var.network_name}-deny-ingress-to-data"
  network     = var.network_name
  description = "Explicitly deny and log any direct access attempts from Ingress to Data Subnet"

  direction = "INGRESS"
  priority  = 950 # Higher priority than default rules

  source_ranges = [var.subnet_public_cidr]
  target_tags   = ["data-db", "data-pipeline"]

  deny {
    protocol = "all"
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}
