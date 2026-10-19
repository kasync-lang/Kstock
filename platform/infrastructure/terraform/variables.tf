variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resource deployment (default: Singapore)"
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  description = "GCP zone for compute instances"
  type        = string
  default     = "asia-southeast1-b"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

# Network CIDRs
variable "vpc_name" {
  description = "Name of the custom VPC network"
  type        = string
  default     = "kstock-vpc"
}

variable "subnet_public_cidr" {
  description = "CIDR block for Tier 1: Public Ingress Subnet"
  type        = string
  default     = "10.10.10.0/24"
}

variable "subnet_backend_cidr" {
  description = "CIDR block for Tier 2: Private Backend Subnet"
  type        = string
  default     = "10.10.20.0/24"
}

variable "subnet_data_cidr" {
  description = "CIDR block for Tier 3: Restricted Data & Pipeline Subnet"
  type        = string
  default     = "10.10.30.0/24"
}

# Static Internal IPs
variable "ingress_internal_ip" {
  description = "Static internal IP for Ingress VM (Nginx)"
  type        = string
  default     = "10.10.10.10"
}

variable "backend_internal_ip" {
  description = "Static internal IP for Backend VM"
  type        = string
  default     = "10.10.20.10"
}

variable "data_internal_ip" {
  description = "Static internal IP for Data & Pipeline VM"
  type        = string
  default     = "10.10.30.10"
}

# Machine Sizing
variable "ingress_machine_type" {
  description = "Compute instance machine type for Nginx Ingress"
  type        = string
  default     = "e2-small"
}

variable "backend_machine_type" {
  description = "Compute instance machine type for Backend (Go & FastAPI)"
  type        = string
  default     = "e2-medium"
}

variable "data_machine_type" {
  description = "Compute instance machine type for Data & Pipeline (ClickHouse, Kafka, Postgres, Redis, Airflow)"
  type        = string
  default     = "e2-standard-4"
}

variable "data_disk_size_gb" {
  description = "Size in GB for dedicated persistent SSD disk for database storage"
  type        = number
  default     = 100
}
