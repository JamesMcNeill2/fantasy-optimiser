provider "aws" {
    region = "eu-west-2"
}

terraform {
    backend "s3" {
        key          = "infra/live/terraform.tfstate"
        region       = "eu-west-2"
        encrypt      = true
        use_lockfile = true
    }
}