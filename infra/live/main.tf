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
  league_ids         = var.league_ids
}

module "batch" {
  source = "../modules/batch"

  name_prefix = local.name_prefix
  image_uri   = "${module.ecr.repository_urls["batch"]}:${var.image_tag}"

  players_table_name = module.data_store.players_table_name
  players_table_arn  = module.data_store.players_table_arn
  users_table_name   = module.data_store.users_table_name
  users_table_arn    = module.data_store.users_table_arn
  league_ids         = var.league_ids
  avatars_bucket     = module.frontend.bucket_name

  schedule_expression = local.batch_schedule
  schedule_state      = startswith(terraform.workspace, "feature-") ? "DISABLED" : "ENABLED"
}

module "frontend" {
  source            = "../modules/frontend"
  name_prefix       = local.name_prefix
  force_destroy     = startswith(terraform.workspace, "feature-")
  api_origin_domain = trimprefix(module.api.api_endpoint, "https://")
}

locals {
  # Batch run times (Europe/London). Each run contains a Sleeper /players
  # call, so no two environments run on the same day.
  batch_schedules = {
    prod = "cron(0 9 ? * THU,SUN *)"
    dev  = "cron(0 9 ? * TUE *)"
  }
  # Feature environments' schedules are disabled; they take dev's expression.
  batch_schedule = lookup(local.batch_schedules, terraform.workspace, local.batch_schedules["dev"])
}
