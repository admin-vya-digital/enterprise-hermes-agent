# Vya Digital Workforce — hermes-agent patchado + vya-workforce-api
#
# Multi-stage: uma base comum (hermes-agent + venv + WhatsApp bridge +
# dashboard web) e dois alvos finais que viram duas imagens/containers
# separados: "hermes-agent" (gateway/dashboard) e "api" (vya-workforce-api).
# skills/ e profiles/ NÃO são copiados para a imagem — são sempre volumes
# (ver docker-compose.yaml), pois mudam em runtime.

# ---------------------------------------------------------------------------
# Base: hermes-agent + venv + WhatsApp bridge + dashboard web
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS hermes-base

# Node é usado pelo bridge do WhatsApp e pelo build do dashboard web
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git procps \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY hermes-agent/ hermes-agent/
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# venv do hermes (reusado pelo target "api" para instalar suas dependências)
RUN python -m venv hermes-agent/venv \
    && hermes-agent/venv/bin/pip install --no-cache-dir --upgrade pip \
    && hermes-agent/venv/bin/pip install --no-cache-dir -e ./hermes-agent

# bridge do WhatsApp (deps node ficam na imagem)
RUN cd hermes-agent/scripts/whatsapp-bridge && npm install --no-audit --no-fund

# dashboard web (builda para hermes_cli/web_dist e descarta node_modules)
RUN cd hermes-agent/web \
    && npm install --no-audit --no-fund \
    && npm run build \
    && rm -rf node_modules

# TUI (aba "Chat" do dashboard, /api/pty spawna "hermes --tui" via ui-tui) —
# sem isso, a primeira mensagem do chat tenta "npm install" on-the-fly, falha
# (sem acesso à internet/registry em runtime) e o processo morre, derrubando
# o WebSocket com "session ended (code 1006)".
RUN cd hermes-agent/ui-tui && npm install --no-audit --no-fund

# profiles/ e skills/ são sempre volumes — só garantimos que existam como
# pontos de montagem
RUN mkdir -p profiles skills

ENTRYPOINT ["/app/entrypoint.sh"]

# ---------------------------------------------------------------------------
# Target "hermes-agent" — gateway/dashboard (container próprio)
# ---------------------------------------------------------------------------
FROM hermes-base AS hermes-agent

EXPOSE 9119

CMD ["/app/hermes-agent/venv/bin/hermes", "dashboard", "--host", "0.0.0.0", "--no-open"]

# ---------------------------------------------------------------------------
# Target "api" — vya-workforce-api (container próprio, reusa o venv da base)
# ---------------------------------------------------------------------------
FROM hermes-base AS api

COPY hermes-api/ hermes-api/
RUN hermes-agent/venv/bin/pip install --no-cache-dir -r hermes-api/requirements.txt

EXPOSE 8700

CMD ["/app/hermes-api/start.sh"]
