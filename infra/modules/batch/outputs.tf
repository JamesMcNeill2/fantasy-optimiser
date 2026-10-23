output "function_name" { value = aws_lambda_function.batch.function_name }
output "function_arn" { value = aws_lambda_function.batch.arn }
output "schedule_name" { value = aws_scheduler_schedule.batch.name }
