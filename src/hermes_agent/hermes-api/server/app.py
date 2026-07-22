"""
vya-workforce-api — FastAPI, porta 8700, Bearer auth, OpenAPI/Swagger.
Plano de controle para criação e manutenção de agentes Hermes.
NUNCA invoca LLM, agente Root ou qualquer canal de conversa.
"""

import os
import time
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import hermes_fs as fs
import whatsapp as wa
from contacts import CONTACT_TYPES, delete_contact, get_contact, list_contacts, set_contact
from knowledge import extract_text, save_knowledge
from lifecycle import delete_profile, inject_knowledge_rule, update_profile
from provision import create_profile
from skills import list_skills, set_skills
from calendar_wrap import (
    calendar_status,
    calendar_create_event,
    calendar_store_client_secret,
    calendar_auth_url,
    calendar_exchange_code,
)
from followup import create_followup, list_followups, delete_followup

# ── Auth ──────────────────────────────────────────────────────────────────────

VYA_API_KEY = os.environ.get("VYA_API_KEY", "")
_bearer = HTTPBearer(auto_error=True)


def _auth(creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)]):
    if not VYA_API_KEY:
        raise HTTPException(503, "VYA_API_KEY não configurada no servidor.")
    if creds.credentials != VYA_API_KEY:
        raise HTTPException(401, "API key inválida.")


AuthDep = Annotated[None, Depends(_auth)]

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Vya Digital Workforce API",
    description=(
        "Plano de controle para agentes Hermes — criação, edição e manutenção via REST.\n\n"
        "Todas as rotas (exceto `/health`) exigem `Authorization: Bearer <VYA_API_KEY>`."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas de request ────────────────────────────────────────────────────────

class CreateAgentBody(BaseModel):
    model_config = {"json_schema_extra": {
        "example": {
            "agent_id": "vya-sdr-01",
            "name": "SDR Vya",
            "description": "SDR digital para qualificação de leads B2B no WhatsApp.",
            "objective": "Qualificar leads, entender a necessidade do cliente e agendar reunião com o time comercial.",
            "personality": "Consultivo, empático, direto e profissional. Nunca pressiona o lead.",
            "language": "pt-BR",
            "model": "claude-haiku-4-5-20251001",
            "temperature": 0.5,
            "initial_prompt": "Sempre encerre a conversa oferecendo um próximo passo claro ao lead.",
            "provider": "anthropic",
            "provider_api_key": "sk-ant-v7-...",
            "whatsapp_mode": "bot",
            "whatsapp_owner_number": ""
        }
    }}

    agent_id: str = Field(
        ...,
        description=(
            "Identificador único do agente. Usado como nome da pasta em "
            "`profiles/<agent_id>/`. "
            "Aceita apenas letras, números e hífens. Não pode ser alterado depois."
        ),
        example="vya-sdr-01",
    )
    name: str = Field(
        ...,
        description="Nome de exibição do agente — aparece no SOUL.md e nas conversas.",
        example="SDR Vya",
    )
    description: str = Field(
        "",
        description="Descrição curta do papel do agente (1–2 frases). Usada no SOUL e no produto.md.",
        example="SDR digital para qualificação de leads B2B no WhatsApp.",
    )
    objective: str = Field(
        "",
        description=(
            "Missão principal do agente em linguagem natural. "
            "Inserida diretamente no SOUL.md como diretriz de comportamento."
        ),
        example="Qualificar leads, entender a necessidade do cliente e agendar reunião com o time comercial.",
    )
    personality: str = Field(
        "",
        description=(
            "Traços de personalidade que definem o tom de comunicação do agente. "
            "Quanto mais específico, mais consistente será o comportamento."
        ),
        example="Consultivo, empático, direto e profissional. Nunca pressiona o lead.",
    )
    language: str = Field(
        "pt-BR",
        description="Idioma principal das respostas do agente (BCP-47).",
        example="pt-BR",
    )
    model: str = Field(
        "",
        description=(
            "ID do modelo de IA a usar. Vazio = herda o padrão do ambiente Hermes. "
            "Exemplos: `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`."
        ),
        example="claude-haiku-4-5-20251001",
    )
    temperature: Optional[float] = Field(
        None,
        description=(
            "Criatividade das respostas: 0.0 = determinístico, 1.0 = muito criativo. "
            "Recomendado entre 0.3–0.7 para SDR. Vazio = padrão do modelo."
        ),
        example=0.5,
    )
    initial_prompt: str = Field(
        "",
        description=(
            "Instrução extra inserida no final do SOUL.md. Use para personalizar "
            "comportamentos específicos que não se encaixam nos campos acima."
        ),
        example="Sempre encerre a conversa oferecendo um próximo passo claro ao lead.",
    )
    provider: str = Field(
        ...,
        description=(
            "Provedor de LLM. Exemplos: 'anthropic', 'openai', 'ollama'. "
            "A chave de API correspondente deve estar em `provider_api_key`."
        ),
        example="anthropic",
    )
    provider_api_key: str = Field(
        ...,
        description="Chave de API do provedor LLM escolhido.",
        example="sk-ant-v7-...",
    )
    whatsapp_mode: str = Field(
        "bot",
        description=(
            "Modo do canal WhatsApp: `bot` (número dedicado, atende só clientes), "
            "`self-chat` (dono conversa com o próprio agente), ou `mixed` (mesmo "
            "número atende o dono E clientes — instala o plugin whatsapp-mixed, "
            "que silencia o bot 10min quando o dono responde manualmente um cliente)."
        ),
        example="mixed",
    )
    whatsapp_owner_number: str = Field(
        "",
        description=(
            "Número do dono do WhatsApp (E.164 sem `+`). Obrigatório se "
            "`whatsapp_mode='mixed'` — é como o plugin distingue 'dono falando "
            "consigo mesmo' de 'dono respondendo um cliente manualmente'."
        ),
        example="5511999999999",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "agent_id": "vya-sdr-01",
                "name": "SDR Vya",
                "description": "SDR digital para qualificação de leads B2B no WhatsApp.",
                "objective": "Qualificar leads, entender a necessidade do cliente e agendar reunião com o time comercial.",
                "personality": "Consultivo, empático, direto e profissional. Nunca pressiona o lead.",
                "language": "pt-BR",
                "model": "claude-haiku-4-5-20251001",
                "temperature": 0.5,
                "initial_prompt": "Sempre encerre a conversa oferecendo um próximo passo claro ao lead.",
            }
        }
    }


class UpdateAgentBody(BaseModel):
    name: Optional[str] = Field(
        None,
        description="Novo nome de exibição. Deixe vazio para não alterar.",
        example="SDR Vya Premium",
    )
    description: Optional[str] = Field(
        None,
        description="Nova descrição curta do agente.",
        example="SDR digital especializado em leads enterprise.",
    )
    objective: Optional[str] = Field(
        None,
        description="Nova missão principal — reescreve o bloco correspondente no SOUL.md.",
        example="Focar em leads com mais de 200 funcionários e agendar demos técnicas.",
    )
    personality: Optional[str] = Field(
        None,
        description="Novos traços de personalidade — reescreve o bloco no SOUL.md.",
        example="Mais técnico e objetivo. Usa dados e benchmarks para convencer.",
    )
    language: Optional[str] = Field(
        None,
        description="Novo idioma principal (BCP-47).",
        example="en-US",
    )
    model: Optional[str] = Field(
        None,
        description="Troca o modelo de IA. O agente usa o novo modelo na próxima conversa.",
        example="claude-sonnet-4-6",
    )
    temperature: Optional[float] = Field(
        None,
        description="Ajusta a criatividade das respostas (0.0–1.0).",
        example=0.3,
    )
    initial_prompt: Optional[str] = Field(
        None,
        description="Substituiu a instrução extra no final do SOUL.md.",
        example="Priorize sempre mostrar ROI e tempo de implantação.",
    )
    provider: Optional[str] = Field(
        None,
        description="Trocar o provedor de LLM. Reescreve a config do perfil.",
        example="openai",
    )
    provider_api_key: Optional[str] = Field(
        None,
        description="Trocar a chave de API do provedor.",
        example="sk-...",
    )
    whatsapp_mode: Optional[str] = Field(
        None,
        description="Trocar o modo do canal WhatsApp: `bot`, `self-chat` ou `mixed`.",
        example="mixed",
    )
    whatsapp_owner_number: Optional[str] = Field(
        None,
        description="Trocar/definir o número do dono (E.164 sem `+`). Necessário para `whatsapp_mode='mixed'`.",
        example="5511999999999",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "claude-sonnet-4-6",
                "temperature": 0.3,
                "personality": "Mais técnico e objetivo. Usa dados e benchmarks para convencer.",
            }
        }
    }


class KnowledgeUrlBody(BaseModel):
    url: str = Field(
        ...,
        description=(
            "URL pública para extrair o conteúdo. Suporta páginas HTML e arquivos de texto. "
            "O conteúdo é salvo em `profiles/<agent_id>/knowledge/<filename>.md`."
        ),
        example="https://vya.digital/sobre",
    )
    filename: str = Field(
        "knowledge",
        description=(
            "Nome base do arquivo salvo (sem extensão). "
            "O arquivo final fica em `knowledge/<filename>.md`."
        ),
        example="sobre-vya",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://vya.digital/sobre",
                "filename": "sobre-vya",
            }
        }
    }


class SkillsBody(BaseModel):
    enable: list[str] = Field(
        [],
        description=(
            "Toolsets a habilitar neste perfil. "
            "Use `GET /agents/{id}/skills` para ver os nomes disponíveis."
        ),
        example=["web", "vision"],
    )
    disable: list[str] = Field(
        [],
        description="Toolsets a desabilitar neste perfil.",
        example=["image_gen"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "enable": ["web", "vision", "calendar"],
                "disable": ["image_gen"],
            }
        }
    }


class CalendarEventBody(BaseModel):
    summary: str = Field(
        ...,
        description="Título do evento no Google Calendar.",
        example="Reunião de apresentação — Vya Digital",
    )
    start: str = Field(
        ...,
        description="Data/hora de início em ISO 8601 com timezone. Ex: '2026-07-10T14:00:00-03:00'.",
        example="2026-07-10T14:00:00-03:00",
    )
    end: str = Field(
        ...,
        description="Data/hora de término em ISO 8601 com timezone.",
        example="2026-07-10T15:00:00-03:00",
    )
    location: str = Field(
        "",
        description="Local do evento (endereço ou link de videoconferência).",
        example="https://meet.google.com/abc-defg-hij",
    )
    description: str = Field(
        "",
        description="Descrição ou pauta do evento.",
        example="Demo do produto para lead qualificado pelo SDR.",
    )
    attendees: str = Field(
        "",
        description="E-mails dos participantes separados por vírgula.",
        example="lead@empresa.com,vendas@vya.digital",
    )
    calendar: str = Field(
        "primary",
        description="ID do calendário Google. Use 'primary' para o calendário principal.",
        example="primary",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "summary": "Reunião de apresentação — Vya Digital",
                "start": "2026-07-10T14:00:00-03:00",
                "end": "2026-07-10T15:00:00-03:00",
                "location": "https://meet.google.com/abc-defg-hij",
                "description": "Demo do produto para lead qualificado pelo SDR.",
                "attendees": "lead@empresa.com,vendas@vya.digital",
                "calendar": "primary",
            }
        }
    }


class _GoogleOAuthClientDetails(BaseModel):
    client_id: str = Field(..., example="SEU_CLIENT_ID.apps.googleusercontent.com")
    project_id: str = Field(..., example="seu-projeto-google-cloud")
    auth_uri: str = Field("https://accounts.google.com/o/oauth2/auth")
    token_uri: str = Field("https://oauth2.googleapis.com/token")
    auth_provider_x509_cert_url: str = Field("https://www.googleapis.com/oauth2/v1/certs")
    client_secret: str = Field(..., example="SEU_CLIENT_SECRET")
    redirect_uris: list[str] = Field(default_factory=lambda: ["http://localhost"])


class CalendarClientSecretBody(BaseModel):
    """
    Aceita exatamente o JSON que o Google Cloud Console entrega ao criar um OAuth
    Client ID (botão de download em APIs & Services → Credentials) — cole o
    conteúdo do arquivo direto no body, sem nenhum wrapper.
    """
    installed: Optional[_GoogleOAuthClientDetails] = None
    web: Optional[_GoogleOAuthClientDetails] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "installed": {
                    "client_id": "SEU_CLIENT_ID.apps.googleusercontent.com",
                    "project_id": "seu-projeto-google-cloud",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_secret": "SEU_CLIENT_SECRET",
                    "redirect_uris": ["http://localhost"],
                }
            }
        }
    }


class CalendarAuthCodeBody(BaseModel):
    code: str = Field(
        ...,
        description=(
            "Código de autorização retornado após o usuário aprovar o consentimento OAuth, "
            "ou a URL de callback completa colada inteira (ambos são aceitos)."
        ),
        example="4/0Adeu5B...",
    )


class FollowupBody(BaseModel):
    name: str = Field(
        ...,
        description="Nome descritivo do job de follow-up.",
        example="Follow-up lead João Silva",
    )
    schedule: str = Field(
        ...,
        description=(
            "Quando executar. Formatos aceitos:\n"
            "- Cron: `'0 9 * * *'` (todo dia às 9h)\n"
            "- Intervalo: `'2h'`, `'30m'`, `'1d'`\n"
            "- One-shot: `'2026-07-12T09:00:00'`"
        ),
        example="2h",
    )
    prompt: str = Field(
        ...,
        description=(
            "Instrução que o agente vai executar no follow-up. "
            "Descreva a ação em linguagem natural."
        ),
        example="Envie uma mensagem de follow-up para o lead 5511999999999 perguntando se ele teve chance de avaliar nossa proposta.",
    )
    repeat: Optional[int] = Field(
        None,
        description="Número máximo de execuções. Vazio = executa indefinidamente (ou até o cron ser deletado).",
        example=3,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Follow-up lead João Silva",
                "schedule": "2h",
                "prompt": "Envie uma mensagem de follow-up para o lead 5511999999999 perguntando se ele teve chance de avaliar nossa proposta.",
                "repeat": 3,
            }
        }
    }


class ContactBody(BaseModel):
    contact_type: str = Field(
        ...,
        description=f"Tipo do contato. Valores aceitos: {CONTACT_TYPES}.",
        example="cliente",
    )
    name: str = Field("", description="Nome do contato (opcional).", example="João Silva")
    notes: str = Field(
        "",
        description="Notas livres sobre o contato (opcional). Não é injetado automaticamente no prompt ainda.",
        example="Lead do WhatsApp, interessado no plano Pro.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {"contact_type": "cliente", "name": "João Silva", "notes": "Lead quente."}
        }
    }


class WriteMemoryBody(BaseModel):
    content: str = Field(
        ...,
        description=(
            "Conteúdo em Markdown a ser gravado como memória do contato. "
            "O agente consulta esse arquivo em conversas futuras com o mesmo número."
        ),
        example=(
            "# Perfil do Lead\n"
            "- **Nome:** João Silva\n"
            "- **Empresa:** Acme Corp\n"
            "- **Segmento:** Varejo\n"
            "- **Status:** QUENTE — solicitou demo\n"
            "- **Próximo passo:** Reunião agendada para 2026-07-05"
        ),
    )
    filename: str = Field(
        "perfil.md",
        description=(
            "Nome do arquivo de memória. Use nomes descritivos para organizar "
            "múltiplas memórias do mesmo contato (ex: `perfil.md`, `historico.md`)."
        ),
        example="perfil.md",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "filename": "perfil.md",
                "content": (
                    "# Perfil do Lead\n"
                    "- **Nome:** João Silva\n"
                    "- **Empresa:** Acme Corp\n"
                    "- **Segmento:** Varejo\n"
                    "- **Status:** QUENTE — solicitou demo\n"
                    "- **Próximo passo:** Reunião agendada para 2026-07-05"
                ),
            }
        }
    }


# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "ts": int(time.time())}


# ── /agents ───────────────────────────────────────────────────────────────────

@app.get("/agents", tags=["agents"], summary="Listar todos os agentes")
def list_agents(_: AuthDep):
    """Retorna todos os perfis Hermes existentes com seu estado atual (online/offline, WhatsApp, etc.)."""
    return fs.list_profiles()


@app.get("/agents/{agent_id}", tags=["agents"], summary="Detalhes de um agente")
def get_agent(agent_id: str, _: AuthDep):
    """Retorna o estado completo do agente lido diretamente dos arquivos do perfil."""
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return fs.profile_info(d)


@app.post(
    "/agents",
    status_code=201,
    tags=["agents"],
    summary="Criar agente",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "examples": {
                        "completo": {
                            "summary": "Agente SDR completo com provider Anthropic",
                            "value": {
                                "agent_id": "vya-sdr-01",
                                "name": "SDR Vya",
                                "description": "SDR digital para qualificação de leads B2B no WhatsApp.",
                                "objective": "Qualificar leads, entender a necessidade do cliente e agendar reunião com o time comercial.",
                                "personality": "Consultivo, empático, direto e profissional. Nunca pressiona o lead.",
                                "language": "pt-BR",
                                "model": "claude-haiku-4-5-20251001",
                                "temperature": 0.5,
                                "initial_prompt": "Sempre encerre a conversa oferecendo um próximo passo claro ao lead.",
                                "provider": "anthropic",
                                "provider_api_key": "sk-ant-v7-...",
                                "whatsapp_mode": "bot",
                                "whatsapp_owner_number": ""
                            }
                        }
                    }
                }
            }
        }
    },
)
def create_agent(
    body: CreateAgentBody,
    _: AuthDep
):
    """
    Cria um novo agente SDR de forma **100% determinística** — sem invocar LLM ou agente Root.

    O que acontece internamente:
    - Cria a pasta `profiles/<agent_id>/` com toda a estrutura de diretórios
    - Gera o `SOUL.md` com a persona SDR a partir do template
    - Gera o `produto.md` com o portfólio da empresa (a preencher via PUT)
    - Escreve o `.env` com modelo, idioma, portas alocadas e chaves herdadas do ambiente global
    - Cria symlink do `config.yaml` global
    - **Não sobe o gateway** — o agente só consome LLM quando conectar um canal (WhatsApp/API)
    """
    try:
        profile = create_profile(
            profile_id=body.agent_id,
            name=body.name,
            description=body.description,
            objective=body.objective,
            personality=body.personality,
            language=body.language,
            model=body.model,
            temperature=body.temperature,
            initial_prompt=body.initial_prompt,
            provider=body.provider,
            provider_api_key=body.provider_api_key,
            whatsapp_mode=body.whatsapp_mode,
            whatsapp_owner_number=body.whatsapp_owner_number,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
    return profile


@app.put("/agents/{agent_id}", tags=["agents"], summary="Editar agente")
def edit_agent(agent_id: str, body: UpdateAgentBody, _: AuthDep):
    """
    Edita campos do agente. Apenas os campos enviados são alterados — os demais permanecem intactos.

    - Campos de texto (`name`, `personality`, etc.) reescrevem o bloco correspondente no `SOUL.md`
    - `model` e `temperature` atualizam o `.env` do perfil
    - Se o gateway estiver rodando, faz **restart escopado** automaticamente para aplicar as mudanças
    """
    try:
        return update_profile(
            profile_id=agent_id,
            name=body.name,
            description=body.description,
            objective=body.objective,
            personality=body.personality,
            language=body.language,
            model=body.model,
            temperature=body.temperature,
            initial_prompt=body.initial_prompt,
            provider=body.provider,
            provider_api_key=body.provider_api_key,
            whatsapp_mode=body.whatsapp_mode,
            whatsapp_owner_number=body.whatsapp_owner_number,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.delete("/agents/{agent_id}", status_code=204, tags=["agents"], summary="Deletar agente")
def remove_agent(agent_id: str, _: AuthDep):
    """
    Remove o agente completamente sem deixar resíduos:
    1. Para o gateway pelo PID gravado em `gateway.pid` (SIGTERM → SIGKILL se necessário)
    2. Para o bridge WhatsApp pelo PID em `bridge.pid` (se existir)
    3. Apaga o diretório `profiles/<agent_id>/` inteiro

    **Nota:** `default-profile` é protegido e não pode ser deletado — é o template base.
    """
    if agent_id == "default-profile":
        raise HTTPException(403, "default-profile é protegido e não pode ser deletado.")
    try:
        delete_profile(agent_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/agents/{agent_id}/restart", tags=["agents"], summary="Reiniciar gateway do agente")
def restart_agent(agent_id: str, _: AuthDep):
    """
    Reinicia só o processo do gateway (SIGTERM → SIGKILL se necessário, depois
    sobe de novo) — não mexe no bridge nem na sessão WhatsApp pareada. Mesmo
    par stop_gateway/start_gateway que `update_profile` já usa internamente
    para aplicar mudanças de persona/config com o gateway no ar.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    pid = fs.restart_gateway(d)
    return {"agent_id": agent_id, "respawned": pid is not None, "gateway_pid": pid}


# ── /knowledge ────────────────────────────────────────────────────────────────

@app.get("/agents/{agent_id}/knowledge", tags=["knowledge"], summary="Listar base de conhecimento")
def list_knowledge(agent_id: str, _: AuthDep):
    """Lista os arquivos `.md` salvos em `profiles/<agent_id>/knowledge/`."""
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return fs.list_knowledge(d)


@app.post("/agents/{agent_id}/knowledge", tags=["knowledge"], summary="Adicionar conhecimento via URL")
def add_knowledge_url(agent_id: str, body: KnowledgeUrlBody, _: AuthDep):
    """
    Busca o conteúdo de uma URL, extrai o texto e salva como arquivo `.md` na base de conhecimento.

    O agente passa a consultar esse arquivo automaticamente em conversas futuras
    (uma regra é injetada no `SOUL.md`).
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    try:
        text = extract_text(body.url, body.filename + ".md")
    except RuntimeError as e:
        raise HTTPException(422, str(e))
    dest = save_knowledge(d, body.filename, text)
    inject_knowledge_rule(d, dest.name)
    return {"saved": dest.name, "size": dest.stat().st_size}


@app.post("/agents/{agent_id}/knowledge/upload", tags=["knowledge"], summary="Upload de arquivo de conhecimento")
async def upload_knowledge(
    agent_id: str,
    _: AuthDep,
    file: UploadFile = File(
        ...,
        description="Arquivo a indexar. Formatos suportados: PDF, DOCX, MD, TXT.",
    ),
):
    """
    Faz upload de um arquivo e salva o texto extraído em `profiles/<agent_id>/knowledge/<nome>.md`.

    - **PDF** → extrai texto de todas as páginas (requer `pypdf`)
    - **DOCX** → extrai parágrafos (requer `python-docx`)
    - **MD / TXT** → salvo diretamente

    Após o upload, a regra de consulta ao arquivo é injetada automaticamente no `SOUL.md`.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    data = await file.read()
    try:
        text = extract_text(data, file.filename or "document")
    except RuntimeError as e:
        raise HTTPException(422, str(e))
    dest = save_knowledge(d, Path(file.filename or "document").stem, text)
    inject_knowledge_rule(d, dest.name)
    return {"saved": dest.name, "size": dest.stat().st_size}


# ── /calendar ─────────────────────────────────────────────────────────────────

@app.get("/agents/{agent_id}/calendar/connect", tags=["calendar"], summary="Status da conexão Google Calendar")
def get_calendar_status(agent_id: str, _: AuthDep):
    """
    Verifica se o OAuth do Google Calendar está configurado para ESTE perfil.

    Cada agente tem seu próprio `google_token.json`/`google_client_secret.json` em
    `profiles/<id>/` — não há mais token compartilhado globalmente. Se `connected: false`,
    siga o fluxo: `POST /calendar/connect` (client secret) → `GET /calendar/connect/auth-url`
    → `POST /calendar/connect/auth-code`.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return calendar_status(d)


@app.post("/agents/{agent_id}/calendar/connect", tags=["calendar"], summary="Salvar client secret do Google OAuth")
def connect_calendar_client_secret(agent_id: str, body: CalendarClientSecretBody, _: AuthDep):
    """
    Salva as credenciais do app OAuth (client_secret) para ESTE perfil.

    O body é **exatamente** o JSON que o Google Cloud Console entrega ao criar um OAuth
    Client ID (botão de download em APIs & Services → Credentials — chave `installed` ou
    `web` na raiz, sem nenhum wrapper). Primeiro passo do fluxo de conexão — depois use
    `GET /calendar/connect/auth-url` para gerar a URL de autorização.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    client_secret = body.model_dump(exclude_none=True)
    try:
        calendar_store_client_secret(d, client_secret)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return calendar_status(d)


@app.get(
    "/agents/{agent_id}/calendar/connect/auth-url",
    tags=["calendar"],
    summary="Gerar URL de autorização OAuth",
)
def get_calendar_auth_url(agent_id: str, _: AuthDep):
    """
    Gera a URL de consentimento OAuth do Google para ESTE perfil. Abra no browser, autorize,
    e cole o código (ou a URL de redirect completa) em `POST /calendar/connect/auth-code`.
    Requer que o client secret já tenha sido salvo via `POST /calendar/connect`.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    try:
        return {"auth_url": calendar_auth_url(d)}
    except RuntimeError as e:
        raise HTTPException(422, str(e))


@app.post(
    "/agents/{agent_id}/calendar/connect/auth-code",
    tags=["calendar"],
    summary="Trocar código OAuth pelo token",
)
def exchange_calendar_auth_code(agent_id: str, body: CalendarAuthCodeBody, _: AuthDep):
    """
    Troca o código de autorização (ou a URL de callback colada inteira) pelo token OAuth
    deste perfil. Último passo do fluxo — depois disso `GET /calendar/connect` retorna
    `connected: true`.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    try:
        calendar_exchange_code(d, body.code)
    except RuntimeError as e:
        raise HTTPException(422, str(e))
    return calendar_status(d)


@app.post("/agents/{agent_id}/calendar/schedule", tags=["calendar"], summary="Criar evento no Google Calendar")
def schedule_event(agent_id: str, body: CalendarEventBody, _: AuthDep):
    """
    Cria um evento real no Google Calendar deste perfil via seu próprio OAuth.

    Retorna o `htmlLink` do evento criado — abra no browser para confirmar.
    O agente pode usar esse link para enviar ao lead como confirmação do agendamento.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    status = calendar_status(d)
    if not status.get("connected"):
        raise HTTPException(503, f"Google Calendar não conectado: {status.get('reason')}")
    try:
        return calendar_create_event(
            d,
            summary=body.summary,
            start=body.start,
            end=body.end,
            location=body.location,
            description=body.description,
            attendees=body.attendees,
            calendar=body.calendar,
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))


# ── /followup ─────────────────────────────────────────────────────────────────

@app.get("/agents/{agent_id}/followup", tags=["followup"], summary="Listar jobs de follow-up")
def get_followups(agent_id: str, _: AuthDep):
    """Lista todos os jobs de follow-up criados para este agente no cron do próprio perfil."""
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return list_followups(d, agent_id)


@app.post("/agents/{agent_id}/followup", status_code=201, tags=["followup"], summary="Criar job de follow-up")
def create_followup_job(agent_id: str, body: FollowupBody, _: AuthDep):
    """
    Cria um job de follow-up automático no cron do perfil deste agente.

    O job é gravado em `profiles/<agent_id>/cron/jobs.json` — o mesmo caminho
    que o scheduler do próprio gateway do agente lê (via HERMES_HOME).

    Para disparar manualmente sem esperar o schedule, use
    `POST /agents/{id}/followup/{job_id}/run` (Fase 4).
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    try:
        job = create_followup(
            d,
            agent_id=agent_id,
            name=body.name,
            schedule=body.schedule,
            prompt=body.prompt,
            repeat=body.repeat,
        )
    except Exception as e:
        raise HTTPException(500, str(e))
    return job


@app.delete("/agents/{agent_id}/followup/{job_id}", status_code=204, tags=["followup"], summary="Deletar job de follow-up")
def delete_followup_job(agent_id: str, job_id: str, _: AuthDep):
    """Remove um job de follow-up do cron do perfil pelo ID."""
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    if not delete_followup(d, job_id):
        raise HTTPException(404, f"Job '{job_id}' não encontrado.")


# ── /skills ───────────────────────────────────────────────────────────────────

@app.get("/agents/{agent_id}/skills", tags=["skills"], summary="Listar toolsets do agente")
def get_skills(agent_id: str, _: AuthDep):
    """
    Retorna todos os toolsets disponíveis com o estado `enabled: true/false` para este perfil.

    O estado é lido do campo `ENABLED_TOOLSETS` no `.env` do perfil — não altera o `config.yaml` global.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return list_skills(d)


@app.post("/agents/{agent_id}/skills", tags=["skills"], summary="Habilitar / desabilitar toolsets")
def update_skills(agent_id: str, body: SkillsBody, _: AuthDep):
    """
    Liga ou desliga toolsets no perfil do agente.

    - `enable` → adiciona à lista ativa
    - `disable` → remove da lista ativa
    - Os dois campos podem ser usados juntos na mesma chamada
    - O estado é gravado em `ENABLED_TOOLSETS` no `.env` do perfil (não toca no `config.yaml` global)
    - Retorna a lista completa de toolsets com o novo estado `enabled`
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    try:
        return set_skills(d, body.enable, body.disable)
    except ValueError as e:
        raise HTTPException(422, str(e))


# ── /channels/whatsapp ───────────────────────────────────────────────────────

@app.get(
    "/agents/{agent_id}/channels/whatsapp",
    tags=["channels"],
    summary="Status da conexão WhatsApp",
)
def get_whatsapp_status(agent_id: str, _: AuthDep):
    """
    Retorna o estado do canal WhatsApp do agente: `paired` (já escaneou o QR
    alguma vez), `phase` (`disconnected` / `pairing` / `paired_not_running` /
    `starting` / `connected`), `jid` (identidade WhatsApp após pareamento) e
    os PIDs do bridge/gateway.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return wa.get_status(d)


@app.post(
    "/agents/{agent_id}/channels/whatsapp",
    tags=["channels"],
    summary="Conectar WhatsApp (inicia pareamento ou sobe o gateway)",
)
def connect_whatsapp(agent_id: str, _: AuthDep):
    """
    Idempotente — chamar de novo não duplica processos:
    - **Nunca pareado:** sobe o bridge Baileys em modo `--pair-only`, que gera o QR
      de forma assíncrona. Consulte `GET .../qr` logo em seguida (pode levar alguns
      segundos para o primeiro QR aparecer).
    - **Já pareado:** garante `WHATSAPP_ENABLED=true` e sobe o gateway do agente
      (que reconecta com as credenciais salvas — sem novo QR).
    - **Pareamento em andamento:** não faz nada, apenas retorna o estado atual.

    O scan do QR pelo celular é o único passo manual de todo o plano de controle.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    try:
        return wa.connect(d)
    except RuntimeError as e:
        raise HTTPException(422, str(e))


@app.get(
    "/agents/{agent_id}/channels/whatsapp/qr",
    tags=["channels"],
    summary="Obter QR code de pareamento (imagem PNG)",
)
def get_whatsapp_qr(agent_id: str, _: AuthDep):
    """
    Retorna o QR atual como **imagem PNG real** (`Content-Type: image/png`) — não
    é base64/JSON. O payload que o Baileys emite é uma string de texto simples;
    esta rota converte para PNG sob demanda com a lib `qrcode`.

    O QR expira e é regerado periodicamente pelo Baileys até ser escaneado —
    dê poll nesta rota a cada poucos segundos enquanto `phase == "pairing"`.
    Retorna 404 se ainda não há QR gerado ou se o agente já está pareado.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    png = wa.get_qr_png(d)
    if not png:
        raise HTTPException(404, "QR ainda não disponível. Chame POST .../channels/whatsapp e tente de novo em alguns segundos.")
    return FileResponse(png, media_type="image/png")


@app.delete(
    "/agents/{agent_id}/channels/whatsapp",
    tags=["channels"],
    summary="Desconectar WhatsApp",
)
def disconnect_whatsapp(agent_id: str, forget: bool = False, _: AuthDep = None):
    """
    Para o bridge e o gateway do agente (por PID).

    `forget=true` também apaga a sessão salva (creds do Baileys) — o próximo
    `POST .../channels/whatsapp` vai gerar um QR novo em vez de reconectar.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return wa.disconnect(d, forget=forget)


# ── /contacts ─────────────────────────────────────────────────────────────────

@app.get("/agents/{agent_id}/contacts", tags=["contacts"], summary="Listar contatos do agente")
def get_contacts(agent_id: str, _: AuthDep):
    """Lista todos os contatos classificados (`owner`/`cliente`) deste agente."""
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return list_contacts(d)


@app.get("/agents/{agent_id}/contacts/{phone}", tags=["contacts"], summary="Ler um contato")
def get_contact_route(agent_id: str, phone: str, _: AuthDep):
    """Lê o perfil de um contato. `phone` é E.164 sem `+` (ex: `5511999999999`)."""
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    contact = get_contact(d, phone)
    if not contact:
        raise HTTPException(404, f"Contato '{phone}' não encontrado.")
    return contact


@app.post("/agents/{agent_id}/contacts/{phone}", tags=["contacts"], summary="Criar/atualizar um contato")
def upsert_contact(agent_id: str, phone: str, body: ContactBody, _: AuthDep):
    """
    Cria ou atualiza a classificação de um contato para este agente.

    Usado pelo plugin `whatsapp-mixed` (WHATSAPP_MODE=mixed) para saber quem é
    o dono do número — mas o dono normalmente é espelhado automaticamente via
    `whatsapp_owner_number` em `POST/PUT /agents`, não precisa chamar esta rota
    pra ele. Use esta rota para cadastrar clientes.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    try:
        return set_contact(d, phone, contact_type=body.contact_type, name=body.name, notes=body.notes)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.delete("/agents/{agent_id}/contacts/{phone}", status_code=204, tags=["contacts"], summary="Remover um contato")
def remove_contact(agent_id: str, phone: str, _: AuthDep):
    """Remove a classificação de um contato."""
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    if not delete_contact(d, phone):
        raise HTTPException(404, f"Contato '{phone}' não encontrado.")


# ── /memory ───────────────────────────────────────────────────────────────────

@app.get(
    "/agents/{agent_id}/memory/{contact_uid}",
    tags=["memory"],
    summary="Ler memória de um contato",
)
def get_memory(agent_id: str, contact_uid: str, _: AuthDep):
    """
    Retorna todos os arquivos de memória do contato em
    `profiles/<agent_id>/memories/contacts/<contact_uid>/` — o mesmo caminho que o
    gateway do próprio agente lê (via HERMES_HOME), garantindo isolamento entre agentes.

    O `contact_uid` é o número de telefone E.164 sem o `+` (ex: `5511999999999`).
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return fs.list_contact_memories(d, contact_uid)


@app.post(
    "/agents/{agent_id}/memory/{contact_uid}",
    tags=["memory"],
    summary="Escrever memória de um contato",
)
def write_memory(agent_id: str, contact_uid: str, body: WriteMemoryBody, _: AuthDep):
    """
    Grava um arquivo Markdown de memória para o contato.

    O agente consulta esses arquivos automaticamente antes de responder ao contato,
    o que permite pré-alimentar o contexto de um lead antes da primeira conversa.

    O `contact_uid` é o número de telefone E.164 sem o `+` (ex: `5511999999999`).
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    if not body.content:
        raise HTTPException(422, "Campo 'content' é obrigatório.")
    mem_dir = d / "memories" / "contacts" / contact_uid
    mem_dir.mkdir(parents=True, exist_ok=True)
    dest = mem_dir / body.filename
    dest.write_text(body.content, encoding="utf-8")
    return {"saved": str(dest), "size": dest.stat().st_size}


# ── /logs ─────────────────────────────────────────────────────────────────────

@app.get("/agents/{agent_id}/logs", tags=["observability"], summary="Ver logs do agente")
def get_logs(
    agent_id: str,
    source: str = "gateway",
    lines: int = 100,
    _: AuthDep = None,
):
    """
    Retorna as últimas linhas de um arquivo de log do perfil.

    `source` pode ser: `gateway` (padrão), `bridge`, `errors`, `agent`.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return {"source": source, "lines": fs.tail_log(d, source, lines)}


# ── /runs ─────────────────────────────────────────────────────────────────────

@app.get("/agents/{agent_id}/runs", tags=["observability"], summary="Ver execuções do agente")
def get_runs(agent_id: str, limit: int = 50, _: AuthDep = None):
    """
    Lista as sessões de conversa e execuções de cron do agente, lidas do `state.db`.

    Inclui contadores de tokens, custo estimado e timestamps de início/fim.
    """
    d = fs.safe_profile_path(agent_id)
    if not d:
        raise HTTPException(404, f"Agente '{agent_id}' não encontrado.")
    return fs.list_runs(d, limit)
