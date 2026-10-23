output "function_name" { value = aws_lambda_function.api.function_name }
output "function_arn" { value = aws_lambda_function.api.arn }
output "invoke_arn" { value = aws_lambda_function.api.invoke_arn }
output "api_endpoint" {
  description = "Base URL of the HTTP API (no trailing slash)"
  value       = aws_apigatewayv2_api.http.api_endpoint
}
