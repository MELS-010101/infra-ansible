output "url" {
  value = "http://localhost:${var.host_port}/"
}

output "container_id" {
  value = docker_container.app.id
}
