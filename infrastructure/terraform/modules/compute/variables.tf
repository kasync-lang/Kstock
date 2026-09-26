variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for deployment"
  type        = string
}

variable "zone" {
  description = "GCP Zone for compute instances"
  type        = string
}

# Subnet IDs
variable "subnet_public_ingress_id" {
  description = "ID of Tier 1 Ingress Subnet"
  type        = string
}

variable "subnet_backend_app_id" {
  description = "ID of Tier 2 Backend Subnet"
  type        = string
}

variable "subnet_data_pipeline_id" {
  description = "ID of Tier 3 Data Subnet"
  type        = string
}

# Static Internal IPs
variable "ingress_internal_ip" {
  description = "Static internal IP for Ingress VM"
  type        = string
}

variable "backend_internal_ip" {
  description = "Static internal IP for Backend VM"
  type        = string
}

variable "data_internal_ip" {
  description = "Static internal IP for Data VM"
  type        = string
}

# Machine types
variable "ingress_machine_type" {
  description = "Machine type for Ingress VM"
  type        = string
}

variable "backend_machine_type" {
  description = "Machine type for Backend VM"
  type        = string
}

variable "data_machine_type" {
  description = "Machine type for Data VM"
  type        = string
}

# Disk Sizing
variable "data_disk_size_gb" {
  description = "Storage capacity in GB for dedicated Database Persistent Disk"
  type        = number
}

# Service Accounts
variable "sa_ingress_email" {
  description = "Email of Ingress Service Account"
  type        = string
}

variable "sa_backend_email" {
  description = "Email of Backend Service Account"
  type        = string
}

variable "sa_data_email" {
  description = "Email of Data Service Account"
  type        = string
}
