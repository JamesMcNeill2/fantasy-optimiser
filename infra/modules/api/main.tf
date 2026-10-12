locals {
  function_name = "${var.name_prefix}-api"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "exec" {
  # Deploy role's IamPassRolesToLambda matches the -exec suffix
  name               = "${var.name_prefix}-api-exec"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

data "aws_iam_policy_document" "exec" {
  statement {
    sid     = "ReadTables"
    effect  = "Allow"
    actions = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query"]
    resources = [
      var.players_table_arn,
      var.users_table_arn,
    ]
  }

  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }
}

resource "aws_iam_role_policy" "exec" {
  name   = "api-exec"
  role   = aws_iam_role.exec.name
  policy = data.aws_iam_policy_document.exec.json
}

resource "aws_lambda_function" "api" {
  function_name = local.function_name
  role          = aws_iam_role.exec.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  architectures = ["x86_64"]
  timeout       = var.timeout
  memory_size   = var.memory_size

  environment {
    variables = {
      PLAYERS_TABLE = var.players_table_name
      USERS_TABLE   = var.users_table_name
      LEAGUE_IDS    = join(",", var.league_ids)
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.api,
    aws_iam_role_policy.exec,
  ]
}

resource "aws_apigatewayv2_api" "http" {
  name          = local.function_name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
}

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
