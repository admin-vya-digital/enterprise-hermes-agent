# Pasta .session-time/

## Propósito
Time tracking de sessões de desenvolvimento.

## Estrutura
```
.session-time/
├── README.md
└── sessions.csv    # Registro de tempo
```

## Formato CSV
```csv
date,start,end,duration_minutes,pauses
2026-05-11,09:00,12:30,210,30
```

## Campos
- `date`: YYYY-MM-DD
- `start`: HH:MM
- `end`: HH:MM
- `duration_minutes`: tempo líquido
- `pauses`: tempo de pausas (café, almoço)

## Uso
```bash
# Registrar sessão
python scripts/session-time.py start
python scripts/session-time.py pause
python scripts/session-time.py resume
python scripts/session-time.py end

# Ver relatório
python scripts/session-time.py report --week
```

## Git Status
CSV não é versionado (dados pessoais).
Apenas README.md commitado.

## Sistema Relacionado
- Feature: Session Management System
- Script: `scripts/session-time.py`
