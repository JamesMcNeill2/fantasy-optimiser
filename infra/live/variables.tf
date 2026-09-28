variable "image_tag" {
  description = "Image tag to deploy (the commit SHA). Sent by CI via TF_VAR_image_tag"
  type        = string

  validation {
    condition     = length(trimspace(var.image_tag)) > 0
    error_message = "image_tag must not be empty."
  }
}
