output "nginx_public_ip" {
  description = "Public IP address of Nginx Ingress WAF (Point your domain A-record here)"
  value       = module.compute.nginx_public_ip
}

output "ingress_internal_ip" {
  description = "Internal private IP of the Ingress VM"
  value       = module.compute.ingress_internal_ip
}

output "backend_internal_ip" {
  description = "Internal private IP of the Backend VM"
  value       = module.compute.backend_internal_ip
}

output "data_internal_ip" {
  description = "Internal private IP of the Data & Pipeline VM (Use to configure DB host in Backend .env)"
  value       = module.compute.data_internal_ip
}

output "ssh_commands" {
  description = "Secure SSH commands via Google Cloud IAP (No public IP required)"
  value = {
    ssh_ingress = "gcloud compute ssh ${module.compute.ingress_vm_name} --zone=${var.zone} --tunnel-through-iap"
    ssh_backend = "gcloud compute ssh ${module.compute.backend_vm_name} --zone=${var.zone} --tunnel-through-iap"
    ssh_data    = "gcloud compute ssh ${module.compute.data_vm_name} --zone=${var.zone} --tunnel-through-iap"
  }
}
