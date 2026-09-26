output "firewall_rules" {
  description = "List of created firewall rule names"
  value = [
    google_compute_firewall.allow_internet_to_ingress.name,
    google_compute_firewall.allow_ingress_to_backend.name,
    google_compute_firewall.allow_backend_to_db.name,
    google_compute_firewall.allow_pipeline_internal.name,
    google_compute_firewall.allow_iap_ssh.name,
    google_compute_firewall.deny_ingress_to_data.name
  ]
}
