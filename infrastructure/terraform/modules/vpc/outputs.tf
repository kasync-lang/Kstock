output "network_id" {
  description = "ID of the custom VPC network"
  value       = google_compute_network.custom_vpc.id
}

output "network_name" {
  description = "Name of the custom VPC network"
  value       = google_compute_network.custom_vpc.name
}

output "subnet_public_ingress_id" {
  description = "ID of the Public Ingress Subnet"
  value       = google_compute_subnetwork.subnet_public_ingress.id
}

output "subnet_backend_app_id" {
  description = "ID of the Private Backend App Subnet"
  value       = google_compute_subnetwork.subnet_backend_app.id
}

output "subnet_data_pipeline_id" {
  description = "ID of the Restricted Data & Pipeline Subnet"
  value       = google_compute_subnetwork.subnet_data_pipeline.id
}
