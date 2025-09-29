FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps for building some Python packages (pandas optional compilation)
# Also install curl/gnupg for NodeSource install script
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
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

# Install Node.js (NodeSource). We keep it in the same image to produce node_modules
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

# Copy package files and install Node dependencies
COPY package.json package-lock.json* ./
RUN (npm ci --no-audit --no-fund) || (npm install --no-audit --no-fund)

# Copy project
COPY . .

ENV FLASK_APP=run.py
ENV FLASK_ENV=production

EXPOSE 8000

# Copy and set entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use entrypoint to run migrations then start gunicorn
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "run:app"]
