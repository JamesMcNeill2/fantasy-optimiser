variable "name_prefix" {
  description = "Prefix for all resource names, e.g. fantasy-optimiser-dev"
  type        = string
}

variable "image_uri" {
  description = "Full ECR image URI including the tag: <repository url>:<tag>"
  type        = string
}

variable "players_table_name" {
  description = "Name of the players DynamoDB table, passed to the function as PLAYERS_TABLE"
  type        = string
}

variable "players_table_arn" {
  description = "ARN of the players DynamoDB table, used in the execution role's write policy"
  type        = string
}

variable "users_table_name" {
  description = "Name of the users DynamoDB table, passed to the function as USERS_TABLE"
  type        = string
}

variable "users_table_arn" {
  description = "ARN of the users DynamoDB table, used in the execution role's write policy"
  type        = string
}

variable "log_retention_days" {
  description = "How long CloudWatch keeps the function's logs"
  type        = number
  default     = 14
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 120 # 2 min

  validation {
    condition     = var.timeout >= 1 && var.timeout <= 900 # 15 min
    error_message = "timeout must be between 1 and 900 seconds."
  }
}

variable "memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 512

  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "memory_size must be between 128 and 10240 MB."
  }
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression (cron or rate), evaluated in Europe/London"
  type        = string
  default     = "cron(0 9 ? * SUN *)"
}

variable "schedule_state" {
  description = "Whether the schedule runs: ENABLED or DISABLED (the root disables it on feature workspaces)"
  type        = string

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.schedule_state)
    error_message = "schedule_state must be ENABLED or DISABLED."
  }
}

variable "league_ids" {
  description = "Sleeper league IDs, passed to the Lambda as LEAGUE_IDS"
  type        = list(string)
  sensitive   = true
}

variable "avatars_bucket" {
  description = "Name of the site bucket the batch copies team avatars into, under avatars/ (served by CloudFront at /avatars/)"
  type        = string
}
