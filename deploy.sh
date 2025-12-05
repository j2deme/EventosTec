#!/bin/bash
# deploy.sh

echo "🕗 Actualizando código..."
git pull origin main

echo "🏗️  Reconstruyendo imagen..."
docker compose build --pull --no-cache web

echo "🔄 Reiniciando servicio..."
docker compose up -d --force-recreate --no-deps web

echo "✅ Despliegue completado."