# Vya Digital Workforce — hermes-agent patchado + vya-workforce-api
#
# Multi-stage: uma base comum (hermes-agent + venv + WhatsApp bridge +
# dashboard web) e dois alvos finais que viram duas imagens/containers
# separados: "hermes-agent" (gateway/dashboard) e "api" (vya-workforce-api).
# skills/ e profiles/ NÃO são copiados para a imagem — são sempre volumes
# (ver docker-compose.yaml), pois mudam em runtime.

# ---------------------------------------------------------------------------
# Versão do hermes-agent (upstream NousResearch/hermes-agent) usada no build.
#
# ARGs globais (antes do primeiro FROM) para ficarem visíveis logo no topo do
# arquivo e serem reusáveis por qualquer stage. Pin por SHA de commit
# imutável (não só pela tag) — uma tag pode ser recriada apontando para outro
# commit (git tag -f), o que quebraria a reprodutibilidade e a integridade do
# build silenciosamente. HERMES_AGENT_REF documenta a tag de release
# correspondente só para leitura humana; quem resolve o checkout é
# HERMES_AGENT_SHA.
#
# Atualizar: rode scripts/update_hermes_agent_version.py (consulta a última
# release do GitHub e já reescreve os dois ARGs abaixo).
# ---------------------------------------------------------------------------
ARG HERMES_AGENT_REPO=https://github.com/NousResearch/hermes-agent.git
ARG HERMES_AGENT_REF=v2026.7.7.2
ARG HERMES_AGENT_SHA=9de9c25f620ff7f1ce0fd5457d596052d5159596

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

# hermes-agent é baixado direto do repositório upstream (em vez de copiado da
# pasta local vendorizada) para garantir código atualizado e íntegro a cada
# build. Os ARGs globais precisam ser redeclarados (sem valor) dentro do
# stage para ficarem visíveis aqui — comportamento padrão do Docker.
ARG HERMES_AGENT_REPO
ARG HERMES_AGENT_REF
ARG HERMES_AGENT_SHA
RUN git clone "${HERMES_AGENT_REPO}" hermes-agent \
    && cd hermes-agent \
    && git checkout "${HERMES_AGENT_SHA}" \
    && test "$(git rev-parse HEAD)" = "${HERMES_AGENT_SHA}" \
    && rm -rf .git

# Customizações locais (patches ainda não mergeados upstream — ver
# hermes-agent-patches.diff) aplicadas sobre o código baixado. Todos os 13
# arquivos do diff (inclui o fix de tui_gateway/ws.py e server.py do WS 1006 —
# docs/bugs/BUG_REPORT_WS_1006.md e BUG_REPORT_WS_1006_RECORRENCIA.md — e
# demais customizações de agent/, cron/, gateway/, hermes_state.py,
# scripts/whatsapp-bridge/bridge.js, tools/, plugins/platforms/whatsapp/)
# foram reconciliados manualmente contra HERMES_AGENT_SHA=9de9c25f... em
# 08/07/2026 e testados com "Applied ... cleanly" (zero rejects) nesta
# versão. gateway/platforms/whatsapp.py foi movido para
# plugins/platforms/whatsapp/adapter.py upstream — o diff já aponta para o
# caminho novo. Precisa ser reconciliado de novo a cada bump de
# HERMES_AGENT_SHA.
#
# best-effort: o upstream evolui rápido (releases quase semanais) e o diff
# pode ficar desatualizado antes da tag ser bumped. Usamos --reject em vez de
# deixar o build falhar: os hunks que não baterem viram .rej dentro de
# hermes-agent/ (aparecem no log abaixo) para reconciliação manual, mas o
# build segue — nunca publicamos uma imagem sem as customizações que
# aplicaram, e as que falharem ficam visíveis em vez de silenciosamente
# ausentes.
COPY hermes-agent-patches.diff ./
RUN cd hermes-agent \
    && (git apply --whitespace=fix --reject --verbose ../hermes-agent-patches.diff 2>&1 | tee /tmp/patch-apply.log || true) \
    && if grep -Eq "\.rej$|error:|arquivo ou diretório inexistente|No such file or directory" /tmp/patch-apply.log; then \
        echo "!!! ATENÇÃO: parte(s) do hermes-agent-patches.diff não foram aplicadas contra HERMES_AGENT_REF=${HERMES_AGENT_REF} — reconciliar manualmente (ver log acima e .rej abaixo):"; \
        find . -name "*.rej"; \
    fi \
    && cd .. && rm -f hermes-agent-patches.diff

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
