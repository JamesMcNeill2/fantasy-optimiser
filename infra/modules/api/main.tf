locals {
  function_name = "${var.name_prefix}-api"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days
}

data "data_iam_policy_document" "assume_role" {
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
  name               = "${var.name_prefix}-api-exec"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

data "aws_iam_policy_document" "exec" {
  statement {
    sid     = "ReadTables"
    effect  = "Allow"
    actions = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamoDB:Query"]
    resources = [
      var.player_table_arn,
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
      PLAYERS_TABLE = var.player_table_name
      USERS_TABLE   = var.users_table_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.api,
    aws_iam_role_policy.exec,
  ]
}
