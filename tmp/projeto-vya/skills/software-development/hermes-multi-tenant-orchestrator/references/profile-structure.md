# Estrutura de Perfil — Anatomia

Cada perfil em `~/.hermes/profiles/{id}/` tem o seguinte layout canônico:

```
~/.hermes/profiles/{id}/
├── .env           # Config isolada (perms 600)
├── produto.md     # Contexto de negócio (editável SÓ pelo Home)
├── bridge.pid     # PID atual do bridge (criado na primeira subida)
├── session/       # Baileys state — creds.json + lid-mapping + device-list
└── logs/
    └── bridge.log # Log isolado do perfil
```

## .env (obrigatório)
Ver `templates/profile-env.template` para o starter. Contém:
- **GOVERNANÇA**: PROFILE_ID, BRIDGE_PORT, HOME_NUMBER, SESSION_DIR, BRIDGE_LOG, PRODUCT_FILE
- **WHATSAPP/Baileys (lid-aware)**: 5 vars necessárias (enabled, mode=bot, allowed_users=*, dm_policy=open, group_policy=open)

Perms: 600 (owner read/write only). Editável via `sed` no terminal ou `write_file` no início.

## produto.md (obrigatório)
Ver `templates/produto.md.template` para o starter. Estrutura:
1. Identidade do agente (nome, função, público, tom)
2. Quem é o cliente (nome, segmento, produto)
3. O que o agente sabe fazer
4. O que NÃO deve fazer
5. Regras de negócio (preços, condições)
6. Como escalar para humano
7. Histórico de edições (com timestamps)

Gerado por Hermes Root UMA vez (versão base template). **Nunca mais editado por Root** — só pelo Número Home via mensagem.

## bridge.pid
Arquivo simples com o PID do processo Node.js do bridge. Criado na primeira subida via:
```bash
echo $! > ~/.hermes/profiles/{id}/bridge.pid
```
Usado por STOP/DESTROY para encontrar o processo certo sem varrer por nome (que pode colidir com outros perfis).

## session/
Diretório de estado do Baileys. Contém:
- `creds.json` — credenciais principais (NÃO deletar sem necessidade — força re-QR)
- `app-state-sync-*.json` — estado de sincronização
- `lid-mapping-{phone}.json` e `lid-mapping-{phone}_reverse.json` — mapeamento LID↔phone (criados organicamente)
- `device-list-{lid}.json` — dispositivos conhecidos por LID (aparece quando bot interage)
- `identity-key-{lid}_1.x.json` — chaves de identidade por contato

NUNCA compartilhar session/ entre perfis (cada um tem o seu).

## logs/bridge.log
Log isolado do perfil. Cada perfil escreve no seu próprio log, então:
- Não há mistura de saída de bridges diferentes
- `tail -f ~/.hermes/profiles/{id}/logs/bridge.log` mostra SÓ aquele perfil
- Rotação de log é responsabilidade do operador (fora do escopo do wizard)

## Perms recomendadas
```bash
chmod 600 ~/.hermes/profiles/{id}/.env          # config só owner
chmod 644 ~/.hermes/profiles/{id}/produto.md    # legível por qualquer processo
chmod 755 ~/.hermes/profiles/{id}/              # pasta navegável
chmod 700 ~/.hermes/profiles/{id}/session       # credenciais Baileys só owner
```