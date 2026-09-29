data "aws_caller_identity" "current" {}

locals {
  # S3 bucket names are globally unique; the account ID makes collisions unlikely.
  bucket_name = "${var.name_prefix}-site-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "site" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy

  lifecycle {
    precondition {
      condition     = length(local.bucket_name) <= 63 && can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", local.bucket_name))
      error_message = "Bucket name \"${local.bucket_name}\" must be at most 63 characters of lowercase letters, digits and hyphens. Use a shorter, lowercase branch name."
    }
  }
}
