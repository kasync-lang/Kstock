resource "google_compute_network" "custom_vpc" {
  name                    = var.vpc_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  description             = "Kstock custom VPC with 3 isolated network tiers (Ingress, Backend, Data)"
}

# Tier 1: Public Ingress Subnet
resource "google_compute_subnetwork" "subnet_public_ingress" {
  name                     = "${var.vpc_name}-subnet-public-ingress"
  ip_cidr_range            = var.subnet_public_cidr
  region                   = var.region
  network                  = google_compute_network.custom_vpc.id
  private_ip_google_access = true
  description              = "Public Ingress Subnet for Nginx WAF / Reverse Proxy"
}

# Tier 2: Private Backend Subnet
resource "google_compute_subnetwork" "subnet_backend_app" {
  name                     = "${var.vpc_name}-subnet-backend-app"
  ip_cidr_range            = var.subnet_backend_cidr
  region                   = var.region
  network                  = google_compute_network.custom_vpc.id
  private_ip_google_access = true
  description              = "Private Subnet for Backend Applications (Go API, FastAPI Auth)"
}

# Tier 3: Restricted Data & Pipeline Subnet
resource "google_compute_subnetwork" "subnet_data_pipeline" {
  name                     = "${var.vpc_name}-subnet-data-pipeline"
  ip_cidr_range            = var.subnet_data_cidr
  region                   = var.region
  network                  = google_compute_network.custom_vpc.id
  private_ip_google_access = true
  description              = "Restricted Subnet for Databases (Postgres, ClickHouse, Redis) and Data Pipeline (Kafka, Airflow)"
}
