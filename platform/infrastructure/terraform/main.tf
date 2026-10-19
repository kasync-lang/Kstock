# ==============================================================================
# ROOT MODULE: KSTOCK INFRASTRUCTURE DEPLOYMENT ON GOOGLE CLOUD
# ==============================================================================

# 1. Network Module (Custom VPC & 3 Isolated Subnets)
module "vpc" {
  source              = "./modules/vpc"
  vpc_name            = var.vpc_name
  region              = var.region
  subnet_public_cidr  = var.subnet_public_cidr
  subnet_backend_cidr = var.subnet_backend_cidr
  subnet_data_cidr    = var.subnet_data_cidr
}

# 2. Cloud NAT Module (Allows safe outbound internet access for private subnets)
module "nat" {
  source      = "./modules/nat"
  router_name = "${var.vpc_name}-router"
  nat_name    = "${var.vpc_name}-nat"
  network_id  = module.vpc.network_id
  region      = var.region
}

# 3. Firewall Module (Strict 3-tier network isolation & Zero Trust rules)
module "firewalls" {
  source              = "./modules/firewalls"
  network_name        = module.vpc.network_name
  subnet_public_cidr  = var.subnet_public_cidr
  subnet_backend_cidr = var.subnet_backend_cidr
  subnet_data_cidr    = var.subnet_data_cidr

  depends_on = [module.vpc]
}

# 4. IAM Module (Dedicated Service Accounts with Least Privilege)
module "iam" {
  source     = "./modules/iam"
  project_id = var.project_id
}

# 5. Compute Module (Tiered VMs, Static IPs, Persistent Data Disk for DBs)
module "compute" {
  source     = "./modules/compute"
  project_id = var.project_id
  region     = var.region
  zone       = var.zone

  subnet_public_ingress_id = module.vpc.subnet_public_ingress_id
  subnet_backend_app_id    = module.vpc.subnet_backend_app_id
  subnet_data_pipeline_id  = module.vpc.subnet_data_pipeline_id

  ingress_internal_ip = var.ingress_internal_ip
  backend_internal_ip = var.backend_internal_ip
  data_internal_ip    = var.data_internal_ip

  ingress_machine_type = var.ingress_machine_type
  backend_machine_type = var.backend_machine_type
  data_machine_type    = var.data_machine_type

  data_disk_size_gb = var.data_disk_size_gb

  sa_ingress_email = module.iam.sa_ingress_email
  sa_backend_email = module.iam.sa_backend_email
  sa_data_email    = module.iam.sa_data_email

  depends_on = [
    module.vpc,
    module.firewalls,
    module.nat,
    module.iam
  ]
}
