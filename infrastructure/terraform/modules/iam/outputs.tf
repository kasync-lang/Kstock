output "sa_ingress_email" {
  description = "Email of the Ingress Service Account"
  value       = google_service_account.sa_ingress.email
}

output "sa_backend_email" {
  description = "Email of the Backend Service Account"
  value       = google_service_account.sa_backend.email
}

output "sa_data_email" {
  description = "Email of the Data & Pipeline Service Account"
  value       = google_service_account.sa_data.email
}
