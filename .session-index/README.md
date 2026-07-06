# Pasta .session-index/

## Propósito
SQLite FTS5 database para busca em documentação de sessões.

## Estrutura
```
.session-index/
├── README.md
└── sessions.db     # SQLite database (FTS5)
```

## Database Schema
- Tabela `sessions_fts`: full-text search
- Índice BM25 ranking
- Campos: date, filename, content, metadata

## Uso
```bash
# Buscar em sessões
python scripts/session-search.py "IMP-65"

# Reconstruir índice
python scripts/session-index.py --rebuild
```

## Performance
- Queries: <0.01s (FTS5 otimizado)
- Tamanho típico: ~5MB/100 sessões

## Git Status
Database não é versionado (`.gitignore`).
Apenas README.md commitado.

## Sistema Relacionado
- IMP-51: Session Search System
- Scripts: `session-search.py`, `session-index.py`
