resource "google_compute_router" "nat_router" {
  name    = var.router_name
  network = var.network_id
  region  = var.region

  description = "Cloud Router for outbound Egress NAT from private subnets"
}

resource "google_compute_router_nat" "cloud_nat" {
  name                               = var.nat_name
  router                             = google_compute_router.nat_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
