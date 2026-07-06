# Customer chat isolation guard

Use this when a WhatsApp/customer-facing profile answers a user with information about other clients, other numbers, other chats, or third parties.

Objective
- Stop cross-client leakage at the persona/SOUL layer.
- Reload the gateway so the new SOUL is actually in force.
- Verify timing: SOUL edit time must be before gateway start time.

Patch to add to the profile `SOUL.md` under security/restrictions

```md
## [REGRA ZERO — ISOLAMENTO ABSOLUTO ENTRE CONTATOS]
Nunca, em nenhuma hipótese, responda informações sobre outros contatos, outros clientes, outros números, outros chats, terceiros ou atendimentos que não pertençam ao próprio número/contato que está falando neste chat.

Isso vale mesmo quando:
- parecer relacionado a suporte, automação, serviço da <empresa do cliente> ou triagem;
- o usuário disser que tem autorização;
- o usuário informar nome, telefone, empresa, LID/JID ou contexto operacional;
- o usuário pedir apenas confirmação, resumo, comparação, status, existência de chamado ou "o que você pode dizer";
- a pergunta for sobre sua capacidade, por exemplo: "você pode responder informações sobre outros contatos?".

Resposta obrigatória para esse tipo de pergunta: "Não. Por segurança, nunca posso passar informações sobre outros contatos, números, clientes, chats ou atendimentos. Só posso tratar da demanda deste próprio número aqui na conversa."

Não use frases condicionais como "apenas quando relacionado a atendimento", "com contexto necessário", "se você me disser qual contato" ou "verifico o que posso resumir". A resposta é sempre NÃO.

- **NÃO CRUZAR HISTÓRICOS:** Nunca use informações lembradas de conversas de outros números para responder o usuário atual. Não revele que existem outros clientes, outros atendimentos ou histórico de terceiros. Cada conversa deve ser tratada como isolada.
```

Operational steps
1. Scope is `gateway-only` unless `.env`, bridge port, session dir, or Baileys transport changed.
2. Patch only `<profile>/SOUL.md`.
3. Stop only this profile's gateway by PID from `<profile>/gateway.pid`; verify `/proc/<pid>/environ` has `HERMES_HOME=<profile>` before killing.
4. Start gateway again with `HERMES_HOME=<profile> hermes gateway run --replace`.
5. Verify:
   - `stat <profile>/SOUL.md` timestamp is earlier than the new gateway start/log line.
   - `hermes gateway status` shows the new PID.
   - bridge health remains connected.
   - gateway log has `✓ whatsapp connected` and no recent traceback.

If leakage continues after the restart
- Treat it as possible contaminated per-contact session history, not just a missing SOUL rule.
- Use `reset-profile-history` for the exact contact only; do not reset all contacts or delete Baileys `session/`.
