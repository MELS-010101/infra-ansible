variable "host_port" {
  description = "Порт на хосте для демо-контейнера"
  type        = number
  default     = 8081
}

variable "container_name" {
  description = "Имя контейнера"
  type        = string
  default     = "demo-app-tf"
}
