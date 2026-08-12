resource "docker_image" "app" {
  name = var.image_name
  build {
    context = var.build_context
  }
  keep_locally = true
}

resource "docker_container" "app" {
  name    = var.container_name
  image   = docker_image.app.image_id
  restart = "unless-stopped"

  ports {
    internal = var.internal_port
    external = var.host_port
  }
}
