output "nginx_public_ip" {
  description = "Public IP address of Nginx Ingress"
  value       = google_compute_address.nginx_public_ip.address
}

output "ingress_internal_ip" {
  description = "Internal private IP of Ingress VM"
  value       = google_compute_address.ingress_internal_ip.address
}

output "backend_internal_ip" {
  description = "Internal private IP of Backend VM"
  value       = google_compute_address.backend_internal_ip.address
}

output "data_internal_ip" {
  description = "Internal private IP of Data & Pipeline VM"
  value       = google_compute_address.data_internal_ip.address
}

output "ingress_vm_name" {
  description = "Name of the Ingress VM instance"
  value       = google_compute_instance.ingress_vm.name
}

output "backend_vm_name" {
  description = "Name of the Backend VM instance"
  value       = google_compute_instance.backend_vm.name
}

output "data_vm_name" {
  description = "Name of the Data VM instance"
  value       = google_compute_instance.data_vm.name
}

output "data_disk_name" {
  description = "Name of the dedicated Database Persistent Disk"
  value       = google_compute_disk.data_disk.name
}
