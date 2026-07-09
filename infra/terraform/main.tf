terraform {
  required_version = ">= 1.7"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

# Redes Docker con nombre, persistentes entre reinicios del stack.
# Docker Compose las referencia como `external: true` (ver infra/compose).
resource "docker_network" "core" {
  name = "cine-platform-core"
}

resource "docker_network" "observability" {
  name = "cine-platform-observability"
}

# Volumenes con nombre para los datos que deben sobrevivir a `docker compose down`.
resource "docker_volume" "postgres_data" {
  name = "cine-platform-postgres-data"
}

resource "docker_volume" "minio_data" {
  name = "cine-platform-minio-data"
}

resource "docker_volume" "grafana_data" {
  name = "cine-platform-grafana-data"
}

resource "docker_volume" "redpanda_data" {
  name = "cine-platform-redpanda-data"
}

output "networks" {
  value = {
    core          = docker_network.core.name
    observability = docker_network.observability.name
  }
}

output "volumes" {
  value = {
    postgres_data = docker_volume.postgres_data.name
    minio_data    = docker_volume.minio_data.name
    grafana_data  = docker_volume.grafana_data.name
    redpanda_data = docker_volume.redpanda_data.name
  }
}
