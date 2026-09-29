data "aws_caller_identity" "current" {}

locals {
  function_name = "${var.name_prefix}-batch"
}

resource "aws_cloudwatch_log_group" "batch" {
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
  name               = "${var.name_prefix}-batch-exec"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

data "aws_iam_policy_document" "exec" {
  statement {
    sid     = "WriteTables"
    effect  = "Allow"
    actions = ["dynamodb:BatchWriteItem"]
    resources = [
      var.players_table_arn,
      var.users_table_arn,
    ]
  }

  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.batch.arn}:*"]
  }
}

resource "aws_iam_role_policy" "exec" {
  name   = "batch-exec"
  role   = aws_iam_role.exec.name
  policy = data.aws_iam_policy_document.exec.json
}

resource "aws_lambda_function" "batch" {
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
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.batch,
    aws_iam_role_policy.exec,
  ]
}

data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  # Deploy role's IamPassRolesToScheduler matches the -scheduler suffix
  name               = "${var.name_prefix}-batch-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.batch.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "batch-scheduler"
  role   = aws_iam_role.scheduler.name
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "batch" {
  name                         = "${var.name_prefix}-batch-refresh"
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "Europe/London"
  state                        = var.schedule_state

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.batch.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({})
  }

  depends_on = [aws_iam_role_policy.scheduler]
}
