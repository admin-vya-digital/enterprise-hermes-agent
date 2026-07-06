# Home-channel escalation notifications for WhatsApp tenants

Use this reference when editing a tenant profile so the customer-facing WhatsApp agent notifies the tenant owner/home channel after collecting a request, doubt, problem, or support demand.

## Pattern

1. Confirm the tenant has `WHATSAPP_HOME_CHANNEL` set in `<profile>/.env`.
   - Prefer the connected account `me.lid` from `session/creds.json`.
   - `target="whatsapp"` in `send_message` resolves to this home channel automatically.
2. Edit the tenant `SOUL.md` (or equivalent persona/context file loaded by the gateway), not the global root prompt.
3. Add an instruction in the escalation/pass-the-baton section:
   - after enough context is collected,
   - call `send_message(action="send", target="whatsapp", message="...")`,
   - then continue responding normally to the end user.
4. Avoid duplicate or noisy notifications:
   - do not notify on simple greetings,
   - do not notify while still investigating,
   - notify only once per collected demand,
   - do not notify when the current conversation is already the home/admin chat.
5. Validate with a real `send_message` smoke test if the user asked to configure it now.

## Recommended notification template

```text
🔔 Nova solicitação coletada
Cliente: <nome exibido ou identificador disponível>
Resumo: <resumo em 1-3 linhas>
Dados coletados: <pontos essenciais, erro, sistema, prazo/impacto se houver>
Próximo passo sugerido: <ação humana recomendada>
```

## Operational notes

- This is a tenant-behavior change, so prefer small steps: inspect current health, patch `SOUL.md`, verify home channel, smoke-test send, then report.
- If the edit also changes `.env`, restart the gateway so it reloads env vars. If only `SOUL.md` changes, the gateway evicts/rebuilds cached agents between turns in normal message handling; restart only if verification shows stale behavior.
- Never expose the internal notification mechanism to the customer-facing user.
