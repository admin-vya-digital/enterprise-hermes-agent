# Pasta .memory/

## Propósito
Storage para MCP servers de memória:
- `memory` server: contexto de conversas
- `sequential-thinking` server: raciocínios salvos

## Estrutura
```
.memory/
├── README.md
├── *.json          # Memórias estruturadas
└── *.txt           # Memórias em texto livre
```

## Formato
- JSON: metadados + conteúdo estruturado
- TXT: raciocínios, notas, observações

## Indexação
MCP servers indexam automaticamente este diretório.
Busca disponível via interface de memória.

## Git Status
Esta pasta está no `.gitignore` (memórias são locais).
Apenas este README.md é commitado.

## MCP Configuration
Configurado em `.vscode/mcp.json`:
```json
{
  "memory": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-memory"]
  }
}
```
