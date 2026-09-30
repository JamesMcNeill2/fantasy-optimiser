variable "name_prefix" {
  description = "Prefix for resource names, e.g. fantasy-optimiser-dev."
  type        = string
}

variable "force_destroy" {
  description = "Allow Terraform to delete the bucket even if it contains objects. Set true only for feature workspaces."
  type        = bool
  default     = false
}

variable "api_origin_domain" {
  description = "Domain name of the HTTP API, without scheme or path, e.g. abc123.execute-api.eu-west-2.amazonaws.com."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]+\\.execute-api\\.[a-z0-9-]+\\.amazonaws\\.com$", var.api_origin_domain))
    error_message = "api_origin_domain must be a bare execute-api domain name (no https:// and no trailing slash or path)."
  }
}
