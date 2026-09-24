locals {
  name_prefix = "fantasy-optimiser-${terraform.workspace}"
}

module "data_store" {
  source      = "../modules/data-store"
  name_prefix = local.name_prefix
}

module "ecr" {
  source       = "../modules/ecr"
  name_prefix  = local.name_prefix
  force_delete = startswith(terraform.workspace, "feature-")
}