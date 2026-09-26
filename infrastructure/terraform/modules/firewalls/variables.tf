variable "network_name" {
  description = "Name of the custom VPC network"
  type        = string
}

variable "subnet_public_cidr" {
  description = "CIDR range of the Public Ingress Subnet"
  type        = string
}

variable "subnet_backend_cidr" {
  description = "CIDR range of the Private Backend Subnet"
  type        = string
}

variable "subnet_data_cidr" {
  description = "CIDR range of the Restricted Data & Pipeline Subnet"
  type        = string
}
