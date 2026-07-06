# Validate creds.json Post-Scan (HOME_NUMBER is not source of truth)

> **Regra absoluta**: nunca grave `HOME_NUMBER` (ou qualquer metadado sobre o número do bot) no `.env` ou em `produto.md` ANTES de validar `session/creds.json`. O admin pode informar um número na conversa e escanear o QR com outro.

> Esta referência é consultada por `create-profile`, `edit-profile` e qualquer diagnóstico que precise confirmar a identidade real do bot.

## Por que validar pós-scan

1. **Admin pode errar** — diz "meu número é X" na conversa e escaneia com Y (chip secundário, número do bot que estava em outro lugar, etc.)
2. **Backups `.env` antigos são armadilha** — se o wizard confiar em backup, propaga o erro pra frente
3. **`creds.json` é gerado pelo Baileys** no momento do scan — é a única fonte da verdade sobre QUEM foi autenticado

## Caso real (provisionamento `<CLIENT_ID>`, 2026-06-26)

| Fonte | Número |
|---|---|
| Backup `.env` global antigo | `<NUMERO_ALT_EXEMPLO>` (bot antigo, desativado) |
| Admin disse na conversa | `<NUMERO_ALT_EXEMPLO>` (eco do backup) |
| Admin escaneou QR com | `<NUMERO_HOME_EXEMPLO>` (<operador> <empresa>, real) |
| **`creds.json` revelou** | `phone=<NUMERO_HOME_EXEMPLO>:17@s.whatsapp.net`, `lid=<LID_EXEMPLO_3>:17@lid` |

Sem validação, HOME_NUMBER teria sido gravado errado. Pós-scan mostrou o real.

## Comando de validação

```bash
# Após o admin escanear o QR e bridge mostrar "✅ WhatsApp connected!"
cat ~/.hermes/profiles/<CLIENT_ID>/session/creds.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
m = d.get('me', {})
print(f'phone : {m.get(\"id\")}')
print(f'lid   : {m.get(\"lid\")}')
print(f'name  : {m.get(\"name\")}')"
```

**Saída esperada** (formato Baileys 6.x+):

```
phone : <NUMERO_HOME_EXEMPLO>:17@s.whatsapp.net
lid   : <LID_EXEMPLO_3>:17@lid
name  : <operador> <empresa>
```

## Como interpretar

| Campo | Significado | O que fazer |
|---|---|---|
| `phone` (sem sufixo) | Número de telefone real do bot | Comparar com o que o admin disse. **Se diferente → PARAR e perguntar** |
| `lid` | WhatsApp Business Local ID | Guardar para referência em logs/filtros |
| `name` | Nome de exibição do perfil | Guardar para auditoria |

## Regra de decisão

```
admin_disse_N   = número que o admin forneceu na Phase 1 (string)
creds_phone_N   = creds['me']['id'].split(':')[0]   # remove sufixo :17@s.whatsapp.net

if admin_disse_N == creds_phone_N:
    OK — gravar HOME_NUMBER=creds_phone_N no .env do perfil
else:
    PARAR — perguntar ao admin qual é o real. Não inferir de backups.
    Após confirmação, gravar o número correto.
```

## Onde aplicar

- `create-profile/SKILL.md` Phase 3 → já tem esta validação embutida
- `edit-profile/SKILL.md` Phase 3 → aplicar quando admin pedir troca de HOME_NUMBER (raro; normalmente escaneia novo QR)
- Diagnóstico genérico → se usuário reporta "minha mensagem vai pra outro lugar", comece por aqui

## Não confundir

- `me.id` ≠ LID. LID é `me.lid`. O adapter Python do gateway repassa o LID cru como `user_id`, e a allowlist tem números de telefone — esse é o problema `@lid` (ver `gateway-multi-profile-errors.md`).
- `me.name` é o nome de EXIBIÇÃO que o usuário vê no WhatsApp, não o "business name". Não confiar pra auditoria.
- O número em `me.id` pode ter sufixo `:17` (device ID) — ignorar, pegar só a parte antes dos `:`.