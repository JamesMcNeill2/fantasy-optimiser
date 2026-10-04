variable "image_tag" {
  description = "Image tag to deploy (the commit SHA). Sent by CI via TF_VAR_image_tag"
  type        = string

  validation {
    condition     = length(trimspace(var.image_tag)) > 0
    error_message = "image_tag must not be empty."
  }
}

variable "league_ids" {
  description = "Sleeper league IDs the batch job refreshes users for"
  type        = list(string)
  sensitive   = true

  validation {
    condition = length(var.league_ids) > 0 && alltrue([
      for id in var.league_ids : can(regex("^[0-9]+$", id))
    ])
    error_message = "league_ids must not be a non-empty list of numeric Sleeper league IDs"
  }
}
