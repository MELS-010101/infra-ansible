terraform {
  required_version = ">= 1.5"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# Remote state: локальное S3-совместимое хранилище (MinIO).
# В проде тот же блок указывает на реальный S3 + DynamoDB для блокировок.
# Секреты для лабы хардкодом; в проде — через env/variables.
terraform {
  backend "s3" {
    endpoints = {
      s3 = "http://localhost:9000"
    }
    bucket                      = "terraform-state"
    key                         = "infra-ansible/terraform.tfstate"
    region                      = "us-east-1"
    access_key                  = "minioadmin"
    secret_key                  = "minioadmin"
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    use_path_style              = true
  }
}
