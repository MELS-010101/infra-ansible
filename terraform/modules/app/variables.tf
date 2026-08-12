variable "image_name" {
  description = "Имя собираемого образа"
  type        = string
}

variable "build_context" {
  description = "Путь к Dockerfile (общий с Ansible)"
  type        = string
}

variable "container_name" {
  description = "Имя контейнера"
  type        = string
}

variable "host_port" {
  description = "Порт на хосте"
  type        = number
}

variable "internal_port" {
  description = "Порт внутри контейнера"
  type        = number
  default     = 8080
}
