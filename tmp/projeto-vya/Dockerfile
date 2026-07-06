# Vya Digital Workforce — hermes-agent patchado + vya-workforce-api + dashboard
FROM python:3.12-slim

# Node é usado pelo bridge do WhatsApp e pelo build do dashboard web
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git procps \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY hermes-agent/ hermes-agent/
COPY hermes-api/ hermes-api/
COPY skills/ skills/
COPY README.md hermes-agent-patches.diff ./

# venv do hermes + dependências da API (o start.sh reusa esse venv)
RUN python -m venv hermes-agent/venv \
    && hermes-agent/venv/bin/pip install --no-cache-dir --upgrade pip \
    && hermes-agent/venv/bin/pip install --no-cache-dir -e ./hermes-agent \
    && hermes-agent/venv/bin/pip install --no-cache-dir -r hermes-api/requirements.txt

# bridge do WhatsApp (deps node ficam na imagem)
RUN cd hermes-agent/scripts/whatsapp-bridge && npm install --no-audit --no-fund

# dashboard web (builda para hermes_cli/web_dist e descarta node_modules)
RUN cd hermes-agent/web \
    && npm install --no-audit --no-fund \
    && npm run build \
    && rm -rf node_modules

# perfis são dados de runtime — montar como volume no compose
RUN mkdir -p profiles

EXPOSE 8700 9119

CMD ["/app/hermes-api/start.sh"]
