variable "name_prefix" {
  description = "Prefix for resource names, e.g. fantasy-optimiser-dev"
  type        = string
}

variable "force_destroy" {
  description = "Allow Terraform to delete the bucket even if it contains objects. Set true only for feature workspaces."
  type        = bool
  default     = false
}
