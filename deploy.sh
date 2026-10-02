#!/bin/bash
# deploy.sh
# Aborta en el primer error (set -e): el "✅" solo se imprime si TODO salió bien.
set -euo pipefail

trap 'echo "❌ Despliegue FALLIDO en la línea $LINENO — revisa el paso anterior. Si falló antes de Reiniciando servicio, producción sigue corriendo la imagen anterior." >&2' ERR

echo "🕗 Actualizando código..."
git pull origin main

echo "📌 HEAD: $(git log -1 --oneline)"

echo "🏗️  Reconstruyendo imagen..."
docker compose build --pull --no-cache web

echo "🔄 Reiniciando servicio..."
docker compose up -d --force-recreate --no-deps web

echo "🧹 Limpiando imágenes huérfanas/viejas..."
docker image prune -f

echo "✅ Despliegue completado."
