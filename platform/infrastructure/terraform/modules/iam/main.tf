# Service Account for Nginx Ingress
resource "google_service_account" "sa_ingress" {
  account_id   = "kstock-sa-ingress"
  display_name = "Kstock Ingress Nginx Service Account"
  description  = "Dedicated service account for Nginx Ingress VM"
}

# Service Account for Backend Apps
resource "google_service_account" "sa_backend" {
  account_id   = "kstock-sa-backend"
  display_name = "Kstock Backend Apps Service Account"
  description  = "Dedicated service account for Backend Apps VM"
}

# Service Account for Data & Pipeline
resource "google_service_account" "sa_data" {
  account_id   = "kstock-sa-data"
  display_name = "Kstock Data & Pipeline Service Account"
  description  = "Dedicated service account for Database and Data Pipeline VM"
}

# Baseline roles for writing logs & metrics to Cloud Ops Suite
locals {
  common_roles = [
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter"
  ]
}

resource "google_project_iam_member" "ingress_roles" {
  for_each = toset(local.common_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.sa_ingress.email}"
}

resource "google_project_iam_member" "backend_roles" {
  for_each = toset(local.common_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.sa_backend.email}"
}

resource "google_project_iam_member" "data_roles" {
  for_each = toset(local.common_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.sa_data.email}"
}
