<!--
Criado em: 08/07/2026 11:04
Modificado em: 08/07/2026 11:04
-->

# 🐛 Bug Report — 500 não tratado em `GET /auth/login?provider=basic`

**Status**: ✅ Corrigido (fix adicionado ao `hermes-agent-patches.diff`, aguardando build/deploy)
**Severidade**: P3 — não derruba o container nem outras sessões; falha isolada de uma rota
**Componentes**: `comp/dashboard`, upstream `hermes_cli/dashboard_auth/`, `plugins/dashboard_auth/basic/`
**Reportado em**: 08/07/2026
**Contexto**: observado em `logs/errors.log` do container `dashboard` — a TUI (aba de chat) continuou
funcionando normalmente durante o incidente; o erro é isolado a essa rota HTTP específica.

---

## Sintoma

```
ERROR:    Exception in ASGI application
...
NotImplementedError: BasicAuthProvider is password-only; there is no OAuth redirect flow.
The login page POSTs to /auth/password-login instead.
```

Uma requisição a `GET /auth/login?provider=basic` derruba com 500 (exceção não tratada) em vez de
receber uma resposta de erro limpa.

---

## Diagnóstico

`hermes_cli/dashboard_auth/routes.py` (rota `auth_login`, `GET /auth/login`) existe para o
**round-trip OAuth** (Google, GitHub etc.). Antes de chamar `provider.start_login()`, ela tem uma
guarda para provedores que não suportam esse fluxo:

```python
if not getattr(p, "supports_session", True):
    raise HTTPException(status_code=404, detail=f"Provider does not support interactive login: {provider!r}")
```

`BasicAuthProvider` (`plugins/dashboard_auth/basic/__init__.py`) é um provedor **só-senha** — não
implementa OAuth, e seu `start_login()`/`complete_login()` levantam `NotImplementedError` de
propósito (o login por senha usa `POST /auth/password-login`, uma rota diferente).

O problema: `BasicAuthProvider` **nunca declara** `supports_session = False`. A classe base
(`hermes_cli/dashboard_auth/base.py:179`) default esse atributo para `True`, então a guarda acima
nunca dispara para o provedor `basic` — a chamada cai direto em `start_login()`, que estoura
`NotImplementedError`. Como a rota só captura `ProviderError` (não `NotImplementedError`), a
exceção sobe sem tratamento e vira um 500.

**Confirmação de que é um bug isolado (não sistêmico)**: o provedor `drain`
(`plugins/dashboard_auth/drain/__init__.py:146`) já declara `supports_session = False`
corretamente — é exatamente o padrão pretendido. Só `basic` estava com a flag ausente. O provedor
`self_hosted` (`SelfHostedOIDCProvider`) implementa OAuth de verdade e não precisa da flag.

## Causa raiz

Atributo de capability ausente em `BasicAuthProvider`: falta `supports_session = False` (ao lado do
já existente `supports_password = True`).

## Correção aplicada

`plugins/dashboard_auth/basic/__init__.py`:

```python
class BasicAuthProvider(DashboardAuthProvider):
    name = "basic"
    display_name = "Username & Password"
    supports_password = True
    supports_session = False  # ← adicionado
```

Com isso, `GET /auth/login?provider=basic` passa a retornar `404 Provider does not support
interactive login: 'basic'` (resposta limpa) em vez de 500.

**Validado**: testado com `git apply --check` contra clone limpo de
`HERMES_AGENT_SHA=9de9c25f620ff7f1ce0fd5457d596052d5159596` (aplica limpo) e como parte do patch
completo (14 arquivos, todos "Applied ... cleanly", zero rejects). `py_compile` OK.

Adicionado como 14º bloco em `src/hermes_agent/hermes-agent-patches.diff`.

## O que NÃO foi corrigido (fora do escopo, mas relacionado)

A rota `auth_login` só captura `ProviderError`, não `NotImplementedError` — ou seja, qualquer outro
provedor futuro que esqueça de declarar `supports_session = False` reproduziria o mesmo 500. Não
alteramos `routes.py` porque o fix pontual em `BasicAuthProvider` já resolve o sintoma observado e é
uma mudança de 1 linha vs. mexer em código de rota upstream mais genérico. Se quiser um cinto de
segurança adicional (capturar `NotImplementedError` na rota e converter em 404), é um segundo patch
independente.

## Referências

- `hermes_cli/dashboard_auth/routes.py` — rota `auth_login`
- `hermes_cli/dashboard_auth/base.py:179` — default `supports_session: bool = True`
- `plugins/dashboard_auth/basic/__init__.py` — provedor corrigido
- `plugins/dashboard_auth/drain/__init__.py:146` — referência do padrão correto já existente
