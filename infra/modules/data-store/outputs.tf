output "players_table_name" { value = aws_dynamodb_table.players.name }
output "players_table_arn" { value = aws_dynamodb_table.players.arn }
output "users_table_name" { value = aws_dynamodb_table.users.name }
output "users_table_arn" { value = aws_dynamodb_table.users.arn }