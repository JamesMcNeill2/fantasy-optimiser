output "players_table_name" { value = module.data_store.players_table_name }
output "users_table_name" { value = module.data_store.users_table_name }
output "ecr_repository_urls" {
  description = "ECR repository URLs, keyed by service name"
  value       = module.ecr.repository_urls
}
output "api_function_name" { value = module.api.function_name }
output "api_endpoint" { value = module.api.api_endpoint }
output "batch_function_name" { value = module.batch.function_name }
output "batch_schedule_name" { value = module.batch.schedule_name }
output "frontend_bucket_name" { value = module.frontend.bucket_name }
output "distribution_id" { value = module.frontend.distribution_id }
output "distribution_domain_name" { value = module.frontend.distribution_domain_name }
