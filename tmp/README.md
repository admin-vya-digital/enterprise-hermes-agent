# Pasta tmp/

## Propósito
Armazenamento temporário para:
- Backups de upgrade (`backup-*`)
- Relatórios de atualização (`UPGRADE_REPORT_*`)
- Outputs temporários de testes
- Arquivos intermediários de processamento

## Conteúdo Esperado
```
tmp/
├── README.md
├── backup-sistema-deploy-YYYYMMDD-HHmmss/  # Backups automáticos
├── UPGRADE_REPORT_*.md                      # Relatórios de upgrade
└── *.tmp                                    # Arquivos temporários
```

## Lifecycle
- Backups: mantidos por 30 dias
- Reports: mantidos permanentemente (documentação)
- Arquivos .tmp: deletados após uso

## Git Status
Esta pasta está no `.gitignore` (conteúdo não versionado).
Apenas este README.md é commitado.

## Scripts Relacionados
- `scripts/scaffold.py --upgrade` (gera backups aqui)
- `scripts/cleanup-tmp.sh` (limpa arquivos antigos)
