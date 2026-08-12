# Образ собирается из того же Dockerfile, что использует Ansible
resource "docker_image" "app" {
  name = "infra-demo-app-tf:latest"
  build {
    context = "../roles/app/files"
  }
  keep_locally = true
}

resource "docker_container" "demo_app_tf" {
  name    = var.container_name
  image   = docker_image.app.image_id
  restart = "unless-stopped"

  ports {
    internal = 8080
    external = var.host_port
  }
}
