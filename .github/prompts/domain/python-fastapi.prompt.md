---
mode: agent
description: "Layer 2 Profile — FastAPI async API. Ative declarando 'Modo: FASTAPI. Projeto: [nome].'"
---

# ⚡ Layer 2 Profile — Python FastAPI

> **Como ativar**: no início da sessão declare:
> ```
> Modo: FASTAPI. Projeto: [nome]. Stack: FastAPI + uv + pytest.
> ```
> Este perfil complementa `devops-programming.prompt.md` — ambos devem estar ativos.

---

## 🎯 Contexto do Perfil

Você está no modo **FastAPI async API**. O trabalho envolve construir APIs HTTP assíncronas com Python usando o framework FastAPI. O foco é em:
- **Async-first**: toda I/O deve usar `async/await` e drivers assíncronos
- **Type safety**: Pydantic v2 para validação e serialização, TypeVar para generics
- **Testabilidade**: `httpx.AsyncClient` com `TestClient` do FastAPI
- **Segurança**: autenticação via `fastapi.security`, sem hardcode de segredos

Diferente do modo `devops-programming` genérico, este perfil tem convenções específicas para estrutura de rotas, injeção de dependências e padrões de teste.

---

## 📋 O que o Copilot precisa saber neste modo

| Informação | Exemplos | Obrigatório? |
|------------|----------|-------------|
| **Versão FastAPI** | `>=0.115` | ✅ |
| **Versão Python** | `>=3.11` | ✅ |
| **Banco de dados** | PostgreSQL (asyncpg), SQLite (aiosqlite), sem banco | ✅ |
| **ORM** | SQLAlchemy async, SQLModel, Beanie (MongoDB), nenhum | ✅ |
| **Autenticação** | JWT (python-jose), OAuth2, API Key, nenhuma | ✅ |
| **Gerenciador de pacotes** | `uv` (obrigatório neste template) | ✅ |
| **Estrutura de rotas** | flat (`src/routes/`), nested (`src/api/v1/`) | Recomendado |
| **Background tasks** | Celery + Redis, ARQ, FastAPI BackgroundTasks | Opcional |
| **Cache** | Redis (aioredis), sem cache | Opcional |

---

## 🏗️ Estrutura de Pastas Padrão

```
{project_name}/
├── src/
│   ├── main.py              # FastAPI app factory + lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py        # APIRouter principal (inclui sub-routers)
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── health.py    # GET /health
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Settings via pydantic-settings + .env
│   │   └── security.py      # JWT, hashing (se aplicável)
│   ├── models/              # Pydantic schemas / SQLModel models
│   │   └── __init__.py
│   └── services/            # Lógica de negócio (sem dependência de HTTP)
│       └── __init__.py
├── tests/
│   ├── conftest.py          # fixtures: app, client async, db session
│   ├── unit/
│   └── integration/
├── .env.example             # variáveis sem valores reais
├── pyproject.toml           # PEP 621 + uv
├── uv.lock                  # commitar sempre
├── Dockerfile               # multistage: builder + runtime
├── docker-compose.yml
├── Makefile
└── docs/
```

---

## 🔧 Convenções FastAPI Obrigatórias

### App factory e lifespan

```python
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.api.router import api_router
from src.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: inicializar conexões, caches
    yield
    # shutdown: fechar conexões

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
        # Desabilitar docs em produção:
        docs_url=None if settings.ENV == "production" else "/docs",
        redoc_url=None if settings.ENV == "production" else "/redoc",
    )
    app.include_router(api_router, prefix="/api")
    return app

app = create_app()
```

### Configuração via pydantic-settings

```python
# src/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROJECT_NAME: str = "my-api"
    VERSION: str = "0.1.0"
    ENV: str = "development"
    SECRET_KEY: str  # obrigatório — sem default
    DATABASE_URL: str | None = None

settings = Settings()
```

### Routers e endpoints

```python
# src/api/v1/health.py
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])

@router.get("", status_code=200)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

### Injeção de dependências

- Usar `Annotated[T, Depends(func)]` — nunca `= Depends(...)` diretamente nos parâmetros
- Dependências de sessão de BD via `async_generator` com `yield`
- Dependências de autenticação retornam o usuário ou levantam `HTTPException(401/403)`

---

## 🧪 Padrão de Testes

### conftest.py mínimo

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from src.main import app

@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

### Smoke test padrão

```python
@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### Regras de teste
- Usar `pytest-asyncio` com `asyncio_mode = "auto"` em `pytest.ini`
- Mocks de serviços externos via `respx` (HTTP) ou `unittest.mock.AsyncMock`
- Banco de dados em testes: SQLite em memória (`aiosqlite`) ou fixture com rollback
- Cobertura mínima: 80% — rodar com `uv run pytest --cov=src`

---

## 🔐 Segurança

### Obrigatório em todo projeto FastAPI

- [ ] `SECRET_KEY` nunca hardcoded — via `.env` e `pydantic-settings`
- [ ] `CORS`: `CORSMiddleware` com `allow_origins` explícito (nunca `["*"]` em produção)
- [ ] Rate limiting: `slowapi` ou middleware customizado para endpoints públicos
- [ ] Headers de segurança: `SecurityHeadersMiddleware` ou `starlette-csrf`
- [ ] Input validation 100% via Pydantic — nunca `request.body()` raw em handlers
- [ ] SQL injection: usar ORM/query builder — nunca f-string em queries
- [ ] `bandit` no pre-commit: `uv run bandit -r src/`
- [ ] `pip-audit`: `uv run pip-audit` no CI para detectar CVEs em deps

### .env.example obrigatório

```dotenv
# .env.example — copiar para .env e preencher valores reais
PROJECT_NAME=my-api
ENV=development
SECRET_KEY=CHANGE_ME_generate_with_openssl_rand_hex_32
DATABASE_URL=postgresql+asyncpg://localhost:5432/dbname  # preencher usuário/senha via variáveis de ambiente
```

---

## 🚀 Quick-start

```bash
git clone <repo>
cd {project_name}
uv sync                    # instala deps + cria .venv
cp .env.example .env       # preencher SECRET_KEY obrigatoriamente
make dev                   # uv run uvicorn src.main:app --reload
```

---

## 📦 Dependências Padrão

```toml
# pyproject.toml [project.dependencies]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "respx>=0.21",
    "pytest-cov>=5",
    "ruff>=0.4",
    "bandit>=1.7",
    "pip-audit>=2.7",
]
```

---

## 🔗 Referências

- [Perfil base](devops-programming.prompt.md) — regras genéricas de programação
- [Segurança](devops-security.prompt.md) — controles transversais
- [Profile Descriptor](../../profile-descriptors/python-fastapi.yaml)
- FastAPI docs: https://fastapi.tiangolo.com
