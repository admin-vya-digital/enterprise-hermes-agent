---
name: create-contact-type
summary: Classificar um contato do WhatsApp de um perfil Hermes multi-tenant como `owner` (dono do número) ou `cliente`. Usado pelo plugin whatsapp-mixed para decidir roteamento, silêncio e backlog de mensagens.
description: "Use quando for necessário registrar/consultar o tipo de um contato (`contact_type`) de um agente do project-vya-workforce — quem é o dono do número (assistente pessoal) e quem são os clientes que o bot atende. Referência da sequência de passos; a implementação real vive em server/contacts.py (API REST), não é executada por um agente."
trigger: "Provisionamento de um agente em modo WHATSAPP_MODE=mixed, ou quando o operador precisa cadastrar/atualizar o tipo de um contato específico via POST /agents/{id}/contacts/{phone}."
pitfalls:
  - "SÓ DOIS VALORES POR ENQUANTO: `contact_type` aceita apenas `owner` e `cliente`. Não inventar outros valores (ex: `Amigo`, `Parente`) sem antes expandir CONTACT_TYPES em server/contacts.py — o enum é validado e rejeita qualquer outro string com 422."
  - "O DONO NÃO É IDENTIFICADO PELO ARQUIVO DE CONTATO, E SIM PELO .env: o plugin whatsapp-mixed decide se uma mensagem veio do dono comparando o número do chat com WHATSAPP_OWNER_NUMBER (gravado no .env do perfil via POST/PUT /agents), não lendo contacts/<phone>.json a cada mensagem — isso evita I/O de arquivo por mensagem e evita depender de um cadastro que pode não existir ainda na primeira mensagem do dono. O registro contact_type=owner em contacts/<phone>.json é só para exibição/consistência via GET /agents/{id}/contacts, é espelhado automaticamente quando whatsapp_owner_number é definido em POST/PUT /agents."
  - "NÃO CONFUNDIR COM WHATSAPP_HOME_CHANNEL: esse é um conceito NATIVO do Hermes (gateway/config.py:HomeChannel), usado só para roteamento de destino padrão de jobs de cron — não tem relação com contact_type nem com quem é o 'dono' do número no sentido de assistente pessoal. Não confundir os dois 'home'/'owner'."
  - "contact_type=cliente NÃO MUDA COMPORTAMENTO SOZINHO ainda: hoje é só um rótulo/dado armazenado em profiles/<agent_id>/contacts/<phone>.json — a lógica de roteamento (self-chat vs cliente) usa WHATSAPP_OWNER_NUMBER, não o contact_type do arquivo. Personas/tons por contact_type são um passo futuro, não implementado nesta versão."
  - "CADA AGENTE TEM SEU PRÓPRIO CONJUNTO DE CONTATOS: profiles/<agent_id>/contacts/<phone>.json é isolado por perfil — o mesmo número de telefone pode ser `cliente` de um agente e não existir em outro. Não há tabela global de contatos entre agentes."
---

# Create Contact Type — Classificação de Contatos (owner | cliente)

**Classe de tarefa**: Registrar/consultar o `contact_type` de um número de telefone dentro de um agente Hermes (project-vya-workforce), para uso pelo plugin `whatsapp-mixed` no modo `WHATSAPP_MODE=mixed`.

## Onde vive

- Implementação real: `project-vya-workforce/server/contacts.py`
- Armazenamento: `~/.hermes/profiles/<agent_id>/contacts/<phone>.json`
- Endpoints REST (Bearer auth, iguais aos demais do control plane):
  - `GET /agents/{agent_id}/contacts` — lista todos os contatos do agente
  - `GET /agents/{agent_id}/contacts/{phone}` — lê um contato
  - `POST /agents/{agent_id}/contacts/{phone}` — cria/atualiza `{contact_type, name?, notes?}`
  - `DELETE /agents/{agent_id}/contacts/{phone}` — remove o registro

`phone` é o número E.164 sem `+` (ex: `5511999999999`), mesmo padrão usado em `/memory/{contact_uid}`.

## Passo a passo — cadastrar o dono (owner)

1. Ao criar ou editar o agente, informe `whatsapp_owner_number` em `POST /agents` ou `PUT /agents/{id}`:
   ```json
   { "whatsapp_mode": "mixed", "whatsapp_owner_number": "5511999999999" }
   ```
2. Isso grava `WHATSAPP_OWNER_NUMBER=5511999999999` no `.env` do perfil (fonte de verdade que o plugin lê) **e** espelha automaticamente um registro em `contacts/5511999999999.json` com `contact_type: "owner"` — não é necessário chamar `POST /contacts` manualmente para o dono.
3. Confirmar:
   ```bash
   cat ~/.hermes/profiles/<agent_id>/.env | grep WHATSAPP_OWNER_NUMBER
   cat ~/.hermes/profiles/<agent_id>/contacts/5511999999999.json
   ```

## Passo a passo — cadastrar um cliente

1. `POST /agents/{agent_id}/contacts/5511888888888`
   ```json
   { "contact_type": "cliente", "name": "João Silva", "notes": "Lead do WhatsApp, interessado no plano Pro." }
   ```
2. Confirmar leitura: `GET /agents/{agent_id}/contacts/5511888888888`
3. Listar todos: `GET /agents/{agent_id}/contacts`

## Verificação de que o roteamento está correto

```bash
# 1. WHATSAPP_MODE deve ser "mixed" para o plugin atuar
grep WHATSAPP_MODE ~/.hermes/profiles/<agent_id>/.env

# 2. Plugin instalado no perfil?
ls ~/.hermes/profiles/<agent_id>/plugins/whatsapp-mixed/plugin.yaml

# 3. Owner configurado?
grep WHATSAPP_OWNER_NUMBER ~/.hermes/profiles/<agent_id>/.env
```

Se `WHATSAPP_MODE` não for `mixed`, o plugin faz early-return e não interfere em nada — o perfil se comporta como `bot`/`self-chat` normalmente (ver `templates/plugins/whatsapp-mixed/whatsapp_mixed.py`).
