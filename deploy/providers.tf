provider "google" {
  region = "us-central1"
}

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.13.0"
    }
  }
}
