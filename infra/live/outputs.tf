output "players_table_name" { value = module.data_store.players_table_name }
output "users_table_name" { value = module.data_store.users_table_name }
output "ecr_repository_urls" {
  description = "ECR repository URLs, keyed by service name"
  value       = module.ecr.repository_urls
}