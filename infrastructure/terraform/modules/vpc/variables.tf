variable "vpc_name" {
  description = "Name of the custom VPC network"
  type        = string
}

variable "region" {
  description = "GCP Region for the subnets"
  type        = string
}

variable "subnet_public_cidr" {
  description = "CIDR range for Tier 1: Public Ingress Subnet"
  type        = string
}

variable "subnet_backend_cidr" {
  description = "CIDR range for Tier 2: Private Backend Subnet"
  type        = string
}

variable "subnet_data_cidr" {
  description = "CIDR range for Tier 3: Restricted Data & Pipeline Subnet"
  type        = string
}
