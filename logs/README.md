# Pasta logs/

## Propósito
Armazenamento de logs de execução:
- Logs de aplicação (runtime logs)
- Logs de scripts de automação
- Logs de testes e validações
- Outputs de diagnóstico

## Conteúdo Esperado
```
logs/
├── README.md
├── app-YYYY-MM-DD.log              # Logs da aplicação
├── scaffold-YYYY-MM-DD.log         # Logs do scaffold
├── tests-YYYY-MM-DD.log            # Logs de testes
└── session-*.log                   # Logs de sessão
```

## Rotation Policy
- Logs mantidos por 90 dias (rotação automática)
- Logs de erro mantidos indefinidamente
- Logs de debug deletados após 7 dias

## Git Status
Esta pasta está no `.gitignore` (conteúdo não versionado).
Apenas este README.md é commitado.

## Logging Configuration
- Python: configurado em `pyproject.toml` → `[tool.logging]`
- Scripts: usar `logging.basicConfig()` com arquivo em `logs/`
- Formato padrão: `YYYY-MM-DD HH:MM:SS [LEVEL] message`
