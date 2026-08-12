# Контейнерный слой описан модулем; корень передаёт параметры
module "demo_app_tf" {
  source = "./modules/app"

  image_name     = "infra-demo-app-tf:latest"
  build_context  = "../roles/app/files"
  container_name = var.container_name
  host_port      = var.host_port
}
