# Alocação de Portas — Hermes Root

## Convenção deste ambiente
- Porta inicial: **3000** (convenção `instance-number`)
- Estratégia: **autoincrement de 1** por perfil novo
- Faixa reservada para bridges: 3000–3099
- Faixa reservada para gateway: 8000–8099 (se múltiplos)

## Validação obrigatória
Antes de alocar qualquer porta, valide:
```bash
lsof -i :PORT
# vazio = livre
# qualquer linha = ocupada, tente a próxima
```

## Sequência esperada
| Perfil | Porta | Justificativa |
|---|---|---|
| `jordao-teste` (primeiro) | 3000 | alocação inicial |
| `cliente-2` | 3001 | autoincrement |
| `cliente-3` | 3002 | autoincrement |
| ... | ... | ... |

## REGISTRY.md (fonte da verdade)
Mantenha em `~/.hermes/profiles/REGISTRY.md`:
```markdown
# Port Registry — Hermes Root

| ID do Perfil | Porta | Status | Criado em | Home Number |
|---|---|---|---|---|
| jordao-teste | 3000 | connected | 2026-06-26 | 5513988396616 |
| cliente-2 | 3001 | stopped | 2026-06-27 | 55119... |
```

Atualize o registry em **toda** operação CREATE/START/STOP/DESTROY.

## Helper
`scripts/find-free-port.sh {start_port}` — escaneia portas a partir de N e imprime a primeira livre.