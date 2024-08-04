resource "random_password" "database_password" {
  length      = 16
  min_special = 1
  min_upper   = 1
  min_numeric = 1
}

resource "random_password" "database_root_password" {
  length      = 16
  min_special = 1
  min_upper   = 1
  min_numeric = 1
}

# Enable Secret Manager API
resource "google_project_service" "secretmanager_api" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

# Enable SQL Admin API
resource "google_project_service" "sqladmin_api" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

# Enable Cloud Run API
resource "google_project_service" "cloudrun_api" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

# Creates SQL instance
resource "google_sql_database_instance" "default" {
  name             = "${var.application_name}-pg-1"
  region           = "us-central1"
  database_version = "POSTGRES_13"
  root_password    = random_password.database_root_password.result

  settings {
    tier = "db-f1-micro"
    password_validation_policy {
      min_length                  = 6
      complexity                  = "COMPLEXITY_DEFAULT"
      reuse_interval              = 2
      disallow_username_substring = true
      enable_password_policy      = true
    }
  }
  # set `deletion_protection` to true, will ensure that one cannot accidentally delete this instance by
  # use of Terraform whereas `deletion_protection_enabled` flag protects this instance at the GCP level.
  deletion_protection = false
  depends_on          = [google_project_service.sqladmin_api]
}

# Create database
resource "google_sql_database" "example" {
  name     = var.database_name
  instance = google_sql_database_instance.default.name
}

# Create user
resource "google_sql_user" "database-user" {
  name     = var.database_user
  instance = google_sql_database_instance.default.name
  password = random_password.database_password.result
}

# Create dbuser secret
resource "google_secret_manager_secret" "dbuser" {
  secret_id = "${var.application_name}-dbusersecret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.secretmanager_api]
}

# Attaches secret data for dbuser secret
resource "google_secret_manager_secret_version" "dbuser_data" {
  secret      = google_secret_manager_secret.dbuser.id
  secret_data = var.database_user
}

# Update service account for dbuser secret
resource "google_secret_manager_secret_iam_member" "secretaccess_compute_dbuser" {
  secret_id = google_secret_manager_secret.dbuser.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com" # Project's compute service account
}

# Create dbpass secret
resource "google_secret_manager_secret" "dbpass" {
  secret_id = "${var.application_name}-dbpasssecret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.secretmanager_api]
}

# Attaches secret data for dbpass secret
resource "google_secret_manager_secret_version" "dbpass_data" {
  secret      = google_secret_manager_secret.dbpass.id
  secret_data = random_password.database_password.result
}

# Update service account for dbpass secret
resource "google_secret_manager_secret_iam_member" "secretaccess_compute_dbpass" {
  secret_id = google_secret_manager_secret.dbpass.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com" # Project's compute service account
}

# Create dbname secret
resource "google_secret_manager_secret" "dbname" {
  secret_id = "${var.application_name}-dbnamesecret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.secretmanager_api]
}

# Attaches secret data for dbname secret
resource "google_secret_manager_secret_version" "dbname_data" {
  secret      = google_secret_manager_secret.dbname.id
  secret_data = var.database_name
}

# Update service account for dbname secret
resource "google_secret_manager_secret_iam_member" "secretaccess_compute_dbname" {
  secret_id = google_secret_manager_secret.dbname.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com" # Project's compute service account
}

resource "google_artifact_registry_repository" "default" {
  location      = var.location
  repository_id = var.application_name
  format        = "DOCKER"
}

resource "google_cloud_run_v2_service" "default" {
  name     = "${var.application_name}-cloudrun-service"
  location = var.location

  template {
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello:latest" # Image to deploy

      env {
        name  = "FLASK_ENV"
        value = "production"
      }

      # Sets a environment variable for instance connection name
      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.default.connection_name
      }
      # Sets a secret environment variable for database user secret
      env {
        name = "DB_USER"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.dbuser.secret_id # secret name
            version = "latest"                                      # secret version number or 'latest'
          }
        }
      }
      # Sets a secret environment variable for database password secret
      env {
        name = "DB_PASS"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.dbpass.secret_id # secret name
            version = "latest"                                      # secret version number or 'latest'
          }
        }
      }
      # Sets a secret environment variable for database name secret
      env {
        name = "DB_NAME"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.dbname.secret_id # secret name
            version = "latest"                                      # secret version number or 'latest'
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.default.connection_name]
      }
    }
  }
  client     = "terraform"
  depends_on = [google_project_service.secretmanager_api, google_project_service.cloudrun_api, google_project_service.sqladmin_api]
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}
