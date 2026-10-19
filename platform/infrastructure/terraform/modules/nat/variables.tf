variable "router_name" {
  description = "Name of the Cloud Router"
  type        = string
  default     = "kstock-nat-router"
}

variable "nat_name" {
  description = "Name of the Cloud NAT Gateway"
  type        = string
  default     = "kstock-cloud-nat"
}

variable "network_id" {
  description = "ID of the VPC Network"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Router and NAT"
  type        = string
}
