output "router_name" {
  description = "Name of the Cloud Router"
  value       = google_compute_router.nat_router.name
}

output "nat_name" {
  description = "Name of the Cloud NAT Gateway"
  value       = google_compute_router_nat.cloud_nat.name
}
