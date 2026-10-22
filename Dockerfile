FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps for building some Python packages (pandas optional compilation)
# Also install curl/gnupg for NodeSource install script
RUN apt-get -o Acquire::Retries=3 update \
  && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
  build-essential \
  gcc \
  libpq-dev \
  curl \
  gnupg \
  ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better layer caching
COPY requirements.txt requirements-dev.txt ./

RUN python -m pip install --upgrade pip \
  && pip install -r requirements.txt

# Install Node.js (NodeSource). We keep it in the same image to produce node_modules.
# La descarga va a fichero en vez de `| bash`: en `sh` (sin pipefail) un curl
# fallido seguiría devolviendo 0 a través de la tubería y el error real saldría
# después, desplazado y engañoso, en el apt-get de abajo.
# Límites duros de red: --max-time cubre también la resolución DNS (que
# --connect-timeout no siempre cubre), así que un corte de red en el build pasa
# de ~34 min de colgue a ≤ ~2 min (reintentos incluidos) y el fallo típico sale
# en segundos. apt reintenta con Acquire::Retries=3 (por defecto, 0).
RUN curl -fsSL --connect-timeout 10 --max-time 60 --retry 2 --retry-delay 3 \
      --retry-max-time 120 -o /tmp/nodesource_setup.sh \
      https://deb.nodesource.com/setup_20.x \
  && bash /tmp/nodesource_setup.sh \
  && apt-get -o Acquire::Retries=3 install -y --no-install-recommends nodejs \
  && rm -f /tmp/nodesource_setup.sh \
  && rm -rf /var/lib/apt/lists/*

# Copy package files and install Node dependencies
COPY package.json package-lock.json* ./
RUN (npm ci --no-audit --no-fund) || (npm install --no-audit --no-fund)

# Copy project
COPY . .

# Genera los assets estáticos NO versionados (app/static/vendor/ y
# app/static/css/tailwind.css). Sin este paso la app se sirve sin estilos.
RUN npm run build:static

ENV FLASK_APP=run.py
ENV FLASK_ENV=production

EXPOSE 8000

# Copy and set entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use entrypoint to run migrations then start gunicorn
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "-w", "4", "-k", "gevent", "--timeout", "120", "-b", "0.0.0.0:8000", "run:app"]
