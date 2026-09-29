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

module "api" {
  source = "../modules/api"

  name_prefix = local.name_prefix
  image_uri   = "${module.ecr.repository_urls["api"]}:${var.image_tag}"

  players_table_name = module.data_store.players_table_name
  players_table_arn  = module.data_store.players_table_arn
  users_table_name   = module.data_store.users_table_name
  users_table_arn    = module.data_store.users_table_arn
}

module "batch" {
  source = "../modules/batch"

  name_prefix = local.name_prefix
  image_uri   = "${module.ecr.repository_urls["batch"]}:${var.image_tag}"

  players_table_name = module.data_store.players_table_name
  players_table_arn  = module.data_store.players_table_arn
  users_table_name   = module.data_store.users_table_name
  users_table_arn    = module.data_store.users_table_arn

  schedule_state = startswith(terraform.workspace, "feature-") ? "DISABLED" : "ENABLED"
}
