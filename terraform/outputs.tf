output "app_url" {
  value = "http://localhost:${var.host_port}/"
}

output "container_id" {
  value = docker_container.demo_app_tf.id
}
