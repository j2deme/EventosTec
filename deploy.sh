#!/bin/bash
# deploy.sh — despliegue de EventosTec
#
# Filosofía: el punto de decisión llega PRONTO. Red caída o lenta se detecta
# en ~10 s (preflight); el tope duro del build es 15 min. Ningún escenario te
# deja esperando una hora sin información.
#
# Variables de entorno (todas opcionales):
#   DEPLOY_MIN_SPEED_KBPS=500   Compuerta de velocidad: por debajo, aborta.
#   DEPLOY_ALLOW_SLOW_NET=0     1 = fuerza el build aunque la red sea lenta.
#   DEPLOY_BUILD_TIMEOUT=900    Tope por intento del build, en segundos (0 = sin tope).
#   DEPLOY_BUILD_RETRIES=3      Intentos máximos para errores de RED rápida.
#   DEPLOY_PREFLIGHT=1          0 = salta el preflight (solo diagnóstico).
#
# Reglas:
#   - El "✅" solo se imprime si TODO salió bien.
#   - El tope de build NUNCA se reintenta solo: corta, diagnostica y decides tú.
#   - Los errores de red rápida (segundos por intento) sí se reintentan solos.
set -euo pipefail

# ---------------------------------------------------------------------------
# Log persistente: cada ejecución queda en deploy-logs/deploy-<fecha>.log
# (gitignored). Todo lo que ves en pantalla también va al archivo.
# ---------------------------------------------------------------------------
LOG_DIR="deploy-logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

FASE="inicio"

# Clasifica la causa a partir de las últimas líneas del log: RED / DISCO /
# DOCKER / DESCONOCIDO. Se usa en el reporte de fallo.
clasificar_causa() {
  local txt
  txt=$(tail -n 200 "$LOG_FILE" 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
  if grep -qE 'no space left on device|disk quota exceeded|enospc' <<<"$txt"; then
    echo "DISCO — sin espacio en el filesystem"
  elif grep -qE 'could not resolve|name resolution|temporary failure|connection refused|connection timed out|connection reset|network is unreachable|no route to host|tls handshake|econnreset|etimedout|eai_again|failed to (fetch|download)|unexpected eof|50[234] (bad gateway|service unavailable|gateway time)' <<<"$txt"; then
    echo "RED — fallo de conectividad/DNS/descarga"
  elif grep -qE 'cannot connect to the docker daemon|docker daemon not running|is the docker daemon running|error during connect' <<<"$txt"; then
    echo "DOCKER — el daemon no responde"
  else
    echo "DESCONOCIDO — revisa las últimas líneas y el log completo"
  fi
}

on_error() {
  local code="${1:-?}" linea="${2:-?}"
  trap - ERR        # evita recursión si algo falla dentro del reporte
  set +e
  sleep 1           # deja que tee vuelque lo último al log antes de leerlo
  echo "" >&2
  echo "❌ Despliegue FALLIDO (exit $code) — fase: $FASE, línea: $linea" >&2
  case "$FASE" in
    build|preflight|pull)
      echo "   🛡️  Producción sigue sirviendo la imagen anterior." >&2 ;;
    *)
      echo "   ⚠️  El paso '$FASE' ya había empezado: revisa 'docker compose ps'." >&2 ;;
  esac
  echo "   🔎 Últimas 15 líneas ($LOG_FILE):" >&2
  tail -n 15 "$LOG_FILE" | sed 's/^/   │ /' >&2
  echo "   🔍 Causa clasificada: $(clasificar_causa)" >&2
  echo "   📄 Log completo: $LOG_FILE" >&2
}
# $LINENO y $? se expanden en el momento de ejecutar el trap: línea y código
# del comando que falló.
trap 'on_error "$?" "$LINENO"' ERR

echo "📄 Log de esta ejecución: $LOG_FILE"

# ---------------------------------------------------------------------------
# Preflight (~10 s): antes de tocar nada, responde "¿por qué no va a salir?".
# ---------------------------------------------------------------------------
if [ "${DEPLOY_PREFLIGHT:-1}" != "0" ]; then
  echo "🛰  Preflight: Docker, red y disco..."

  if ! docker info >/dev/null 2>&1; then
    echo "❌ El daemon de Docker no responde. Inicia Docker Desktop (o el servicio docker) y reintenta." >&2
    echo "🔍 Causa clasificada: DOCKER — el daemon no responde" >&2
    exit 1
  fi

  # DNS + TCP + TLS contra los hosts que el build necesita. Un "000" es
  # inalcanzable; cualquier código HTTP (aunque sea 4xx) significa "reachable".
  FALLIDOS=""
  for host in github.com deb.debian.org deb.nodesource.com pypi.org files.pythonhosted.org registry.npmjs.org; do
    code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "https://$host/" || true)
    if [ "$code" = "000" ]; then
      FALLIDOS="$FALLIDOS $host"
    fi
    printf '   %-24s %s\n' "$host" "$code"
  done
  if [ -n "$FALLIDOS" ]; then
    echo "❌ Hosts inalcanzables:$FALLIDOS" >&2
    echo "   Sin estos hosts el build morirá a mitad. Revisa DNS/conexión y reintenta." >&2
    echo "   (DEPLOY_PREFLIGHT=0 lo salta, solo para diagnóstico)" >&2
    echo "🔍 Causa clasificada: RED — fallo de conectividad/DNS/descarga" >&2
    exit 1
  fi

  # Aviso de disco (no fatal): el checkout y el build context necesitan sitio.
  libres_mb=$(df -Pm . | awk 'NR==2 {print $4}')
  if [ -n "${libres_mb:-}" ] && [ "$libres_mb" -lt 3000 ]; then
    echo "⚠️  Poco espacio en el filesystem del checkout: ${libres_mb} MB libres (< 3 GB)."
  fi

  # Compuerta de velocidad: mide el throughput real ~6 s contra deb.debian.org
  # (el anfitrión que el build usa para apt). Aquí es donde la red lenta se
  # detecta en 10 s en vez de a los 36 min de la capa apt:
  #   < DEPLOY_MIN_SPEED_KBPS  → aborta con estimación (fuerza con DEPLOY_ALLOW_SLOW_NET=1)
  #   500–1000 KB/s            → aviso y continúa
  #   ≥ 1 MB/s                 → silencio (build sano ≈ 6 min)
  MIN_KBPS=${DEPLOY_MIN_SPEED_KBPS:-500}
  bps=$(curl -s -m 6 -o /dev/null -w '%{speed_download}' -r 0-2097151 \
        https://deb.debian.org/debian/dists/stable/InRelease || true)
  kbps=$(awk -v b="${bps:-0}" 'BEGIN { printf "%d", b / 1024 }')
  echo "   Velocidad medida contra deb.debian.org: ${kbps} KB/s"
  if [ "$kbps" -lt "$MIN_KBPS" ]; then
    est_min=$(awk -v k="$kbps" 'BEGIN { if (k < 1) k = 1; printf "%d", (200 * 1024) / k / 60 + 0.5 }')
    if [ "${DEPLOY_ALLOW_SLOW_NET:-0}" = "1" ]; then
      echo "⚠️  Red lenta, pero DEPLOY_ALLOW_SLOW_NET=1: continúo (build estimado ≈ ${est_min} min)."
    else
      echo "❌ Red lenta: ${kbps} KB/s (< ${MIN_KBPS} KB/s)." >&2
      echo "   Un build a esta velocidad tomaría ≈ ${est_min} min (baseline sano: ~6 min)." >&2
      echo "   Decide tú: relanza cuando mejore, o fuerza con:  DEPLOY_ALLOW_SLOW_NET=1 ./deploy.sh" >&2
      echo "🔍 Causa clasificada: RED — velocidad insuficiente" >&2
      exit 1
    fi
  elif [ "$kbps" -lt 1024 ]; then
    echo "⚠️  Red regular (≈${kbps} KB/s): el build puede tardar varios minutos de más."
  fi
fi

# ---------------------------------------------------------------------------
# Pull de código
# ---------------------------------------------------------------------------
FASE="pull"
echo "🕗 Actualizando código..."
git pull origin main
echo "📌 HEAD: $(git log -1 --oneline)"

# ---------------------------------------------------------------------------
# Build: tope duro + reintentos solo para errores de red rápida.
#   - Tope (DEPLOY_BUILD_TIMEOUT, por defecto 15 min = 2.5× el baseline de
#     ~6 min): lo único que acota la red "viva pero a gotas", donde ningún
#     comando falla y todo se arrastra. NO se reintenta solo: corta,
#     diagnostica y decides tú.
#   - Reintentos: solo si el fallo huele a red rápida (segundos por intento,
#     backoff 15 s / 30 s). Un SyntaxError no se reintenta: aborta al 1er intento.
# ---------------------------------------------------------------------------
FASE="build"
BUILD_TIMEOUT=${DEPLOY_BUILD_TIMEOUT:-900}
INTENTOS_MAX=${DEPLOY_BUILD_RETRIES:-3}

con_tope() {
  if [ "$BUILD_TIMEOUT" -gt 0 ]; then
    timeout --kill-after=30 "$BUILD_TIMEOUT" "$@"
  else
    "$@"
  fi
}

es_error_de_red() {
  grep -qiE 'could not resolve|name resolution|temporary failure|connection refused|connection timed out|connection reset|network is unreachable|no route to host|tls handshake|econnreset|etimedout|eai_again|failed to (fetch|download)|unexpected eof|50[234] (bad gateway|service unavailable|gateway time)' "$1"
}

intento=1
while true; do
  # Log POR INTENTO: la decisión de reintentar se toma solo con la salida de
  # este intento. Si se escaneara el acumulado, un fallo de red del intento 1
  # haría reintentar un error determinista del intento 2.
  BUILD_LOG="$LOG_DIR/build-$(date +%Y%m%d-%H%M%S)-intento${intento}.log"
  echo "🏗️  Reconstruyendo imagen (intento $intento/$INTENTOS_MAX, tope ${BUILD_TIMEOUT}s)..."
  # El trap ERR se dispara aunque set +e esté activo: hay que quitarlo
  # explícitamente para manejar el código de salida del build a mano.
  set +e
  trap - ERR
  con_tope docker compose build --pull --no-cache web 2>&1 | tee -a "$BUILD_LOG"
  status=${PIPESTATUS[0]}
  trap 'on_error "$?" "$LINENO"' ERR
  set -e

  if [ "$status" -eq 0 ]; then
    break
  fi

  # 124 = GNU timeout dio al tope. Es "red lenta que nada falla", no un error:
  # no se reintenta solo; el humano decide.
  if [ "$status" -eq 124 ]; then
    echo "" >&2
    echo "⏱  BUILD ANÓMALO: tope de ${BUILD_TIMEOUT} s alcanzado (baseline sano: ~6 min)." >&2
    echo "   Última capa con actividad en el log:" >&2
    ultima=$(grep -E '^#[0-9]+' "$BUILD_LOG" | tail -n 2 || true)
    if [ -n "$ultima" ]; then
      printf '   │ %s\n' "$ultima" >&2
    else
      echo "   │ (sin salida de capa: murió antes de emitir — típico de descarga colgada)" >&2
    fi
    echo "   Esto casi siempre es la red a gotas: nada falla, todo se arrastra." >&2
    echo "   Decide tú: relanza cuando mejore, o sube el tope:  DEPLOY_BUILD_TIMEOUT=0 ./deploy.sh" >&2
    echo "   🔍 Causa clasificada: ESTANCAMIENTO/RED LENTA — tope de build" >&2
    echo "   📄 Log del build: $BUILD_LOG" >&2
    exit 124
  fi

  if [ "$intento" -lt "$INTENTOS_MAX" ] && es_error_de_red "$BUILD_LOG"; then
    espera=$((15 * intento))   # 15 s tras el intento 1, 30 s tras el 2
    echo "🌐 Fallo de red rápida (intento $intento). Reintento en ${espera}s..." >&2
    sleep "$espera"
    intento=$((intento + 1))
    continue
  fi

  echo "💥 Build falló (exit $status) sin apariencia de red reintentable: no se reintenta." | tee -a "$BUILD_LOG" >&2
  on_error "$status" "$LINENO"
  exit "$status"
done

# ---------------------------------------------------------------------------
# Recreate + limpieza
# ---------------------------------------------------------------------------
FASE="recreate"
echo "🔄 Reiniciando servicio..."
docker compose up -d --force-recreate --no-deps web

FASE="prune"
echo "🧹 Limpiando imágenes huérfanas/viejas..."
docker image prune -f

echo "✅ Despliegue completado. (log: $LOG_FILE)"
