#!/usr/bin/env bash
# activate-mcp.sh — Valida configuração MCP e auxilia inicialização de servidores
#
# Uso:
#   ./scripts/activate-mcp.sh          # verificação padrão
#   ./scripts/activate-mcp.sh --auto   # tenta abrir Command Palette automaticamente

set -euo pipefail

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
MCP_CONFIG=".vscode/mcp.json"
REQUIRED_SERVERS=("memory" "sequential-thinking")
AUTO_OPEN=false

# Parse argumentos
if [[ "${1:-}" == "--auto" ]]; then
    AUTO_OPEN=true
fi

# Função: log colorido
log_info() { echo -e "${BLUE}ℹ️  ${1}${NC}"; }
log_success() { echo -e "${GREEN}✅ ${1}${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  ${1}${NC}"; }
log_error() { echo -e "${RED}❌ ${1}${NC}"; }

echo ""
echo "🚀 MCP Server Activation Helper"
echo "================================="
echo ""

# Passo 1: Verificar se mcp.json existe
log_info "Verificando se $MCP_CONFIG existe..."

if [[ ! -f "$MCP_CONFIG" ]]; then
    log_error "$MCP_CONFIG não encontrado"
    echo ""
    echo "💡 Sugestão: Execute 'uv run scripts/scaffold.py' para criar a estrutura inicial"
    exit 1
fi

log_success "$MCP_CONFIG encontrado"

# Passo 2: Verificar se é JSON válido (aceita comentários JSONC)
log_info "Validando sintaxe JSON..."

# Validar JSONC (JSON with Comments) - VS Code usa este formato
if ! python3 -c "
import json, re, sys
with open('$MCP_CONFIG') as f:
    content = f.read()
    # Remover comentários de linha única (//)
    content = re.sub(r'//.*', '', content)
    # Remover comentários de bloco (/* ... */)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    try:
        json.loads(content)
        sys.exit(0)
    except json.JSONDecodeError as e:
        print(f'Erro JSON: {e}', file=sys.stderr)
        sys.exit(1)
" 2>/dev/null; then
    log_error "JSON inválido em $MCP_CONFIG"
    exit 1
fi

log_success "JSON válido (JSONC)"

# Passo 3: Verificar servidores necessários
log_info "Verificando servidores configurados..."

MISSING_SERVERS=()
COMMENTED_SERVERS=()

for server in "${REQUIRED_SERVERS[@]}"; do
    # Verificar se o servidor está no arquivo
    if ! grep -q "\"$server\"" "$MCP_CONFIG"; then
        MISSING_SERVERS+=("$server")
        continue
    fi

    # Verificar se a linha com o nome do servidor está comentada
    # Procurar pela linha que contém "nome": { (chave do servidor)
    if grep "\"$server\"[[:space:]]*:" "$MCP_CONFIG" | grep -q "^[[:space:]]*//"; then
        COMMENTED_SERVERS+=("$server")
    fi
done

# Reportar resultados
ALL_OK=true

if [[ ${#MISSING_SERVERS[@]} -gt 0 ]]; then
    ALL_OK=false
    log_error "Servidores não configurados: ${MISSING_SERVERS[*]}"
    echo ""
    echo "💡 Adicione ao $MCP_CONFIG:"
    echo ""
    for server in "${MISSING_SERVERS[@]}"; do
        echo "  \"$server\": {"
        echo "    \"command\": \"npx\","
        echo "    \"args\": [\"-y\", \"@modelcontextprotocol/server-$server\"]"
        echo "  },"
    done
    echo ""
fi

if [[ ${#COMMENTED_SERVERS[@]} -gt 0 ]]; then
    ALL_OK=false
    log_error "Servidores comentados: ${COMMENTED_SERVERS[*]}"
    echo ""
    echo "💡 Descomente as linhas no $MCP_CONFIG"
    echo ""
fi

if [[ "$ALL_OK" == true ]]; then
    log_success "Configuração MCP OK — ${REQUIRED_SERVERS[*]}"
fi

# Passo 4: Listar todos os servidores configurados
log_info "Servidores detectados em $MCP_CONFIG:"
echo ""

# Extrair nomes dos servidores (assumindo padrão "nome": { ... })
python3 -c "
import json, re
with open('$MCP_CONFIG') as f:
    content = f.read()
    # Remover comentários JSONC
    content = re.sub(r'//.*', '', content)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    config = json.loads(content)
    servers = config.get('servers', {})
    if servers:
        for idx, server in enumerate(servers.keys(), 1):
            print(f'  {idx}. {server}')
    else:
        print('  (nenhum servidor encontrado)')
" 2>/dev/null || echo "  (erro ao parsear servidores)"

echo ""

# Passo 5: Instruções para ativar no VS Code
if [[ "$ALL_OK" == true ]]; then
    log_success "Configuração validada com sucesso!"
    echo ""
    log_info "💡 AUTOSTART HABILITADO"
    echo ""
    echo "  Os servidores MCP devem iniciar AUTOMATICAMENTE ao abrir o workspace"
    echo "  devido à configuração 'chat.mcp.autostart: true' em .vscode/settings.json"
    echo ""
    echo "  Se esta é a PRIMEIRA EXECUÇÃO:"
    echo "    • VS Code pode solicitar confirmação de TRUST para cada servidor"
    echo "    • Aceite o trust para permitir inicialização automática futura"
    echo ""
    log_info "Para ATIVAR os servidores MCP MANUALMENTE (se necessário):"
    echo ""
    echo "  1️⃣  Abra o Command Palette (Ctrl+Shift+P / Cmd+Shift+P)"
    echo "  2️⃣  Digite: 'MCP: Refresh Servers'"
    echo "  3️⃣  Aguarde a inicialização dos servidores"
    echo ""
    log_info "Para VERIFICAR se estão rodando:"
    echo ""
    echo "  1️⃣  Command Palette → 'MCP: List Servers'"
    echo "  2️⃣  Confirme que aparecem: ${REQUIRED_SERVERS[*]}"
    echo ""

    # Tentar abrir automaticamente se --auto
    if [[ "$AUTO_OPEN" == true ]]; then
        log_info "Modo --auto: tentando abrir Command Palette..."

        if command -v code-insiders &> /dev/null; then
            CODE_CMD="code-insiders"
        elif command -v code &> /dev/null; then
            CODE_CMD="code"
        else
            log_warning "VS Code CLI não encontrado (code ou code-insiders)"
            log_info "Execute manualmente: Command Palette → 'MCP: Refresh Servers'"
            exit 0
        fi

        # Abrir workspace atual e executar comando
        log_info "Executando: $CODE_CMD . --command workbench.action.showCommands"
        "$CODE_CMD" . --command workbench.action.showCommands || true

        echo ""
        log_warning "Command Palette aberto. Digite manualmente: 'MCP: Refresh Servers'"
    fi
else
    log_error "Corrija os problemas acima antes de ativar os servidores"
    exit 1
fi

echo ""
log_success "Script concluído!"
echo ""
