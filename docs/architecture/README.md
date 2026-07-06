# docs/architecture/ — Documentação de Arquitetura

Diagramas, visões e documentação estrutural do sistema.

## 🎯 Objetivo

Documentar a **estrutura e organização** do sistema.

## 📝 Conteúdo

### 1. Visões Arquiteturais (C4 Model)

```
architecture/
├── context/          # C4 Level 1: System Context
├── containers/       # C4 Level 2: Container Diagram
├── components/       # C4 Level 3: Component Diagram
└── code/            # C4 Level 4: Code (opcional)
```

### 2. Diagramas

- Arquitetura de alto nível
- Fluxo de dados
- Deployment topology
- Integrações externas

### 3. Documentação Estrutural

- Módulos e responsabilidades
- Padrões arquiteturais adotados
- Boundaries e interfaces

## 📝 Template: Documento de Arquitetura

```markdown
# Arquitetura: [Componente/Sistema]

**Última atualização**: YYYY-MM-DD
**Owner**: [Time/Pessoa]

## Visão Geral
[Descrição de alto nível]

## Componentes Principais
### [Nome do Componente]
- **Responsabilidade**: ...
- **Tecnologia**: ...
- **Dependências**: ...

## Decisões Arquiteturais
Ver ADRs relacionados:
- [ADR-001](../decisions/ADR-001-xxx.md)

## Diagramas
![Diagrama Context](./diagrams/context.png)

## Qualidade e Não-Funcionais
- Escalabilidade: ...
- Segurança: ...
- Performance: ...

## Riscos Arquiteturais
- [Risco] — [Mitigação]
```

## 🛠️ Ferramentas sugeridas

- **Mermaid** — Diagramas em Markdown
- **PlantUML** — UML extensivo
- **Draw.io** — Diagramas gerais
- **C4 Model** — Framework de visualização

## 📂 Estrutura sugerida

```
architecture/
├── README.md (este arquivo)
├── overview.md
├── context-diagram.md
├── api-design.md
├── data-model.md
└── diagrams/
    ├── context.mmd
    ├── containers.mmd
    └── deployment.png
```

## 🔗 Ver também

- [decisions/](../decisions/) — ADRs
- [debates/](../debates/) — Discussões arquiteturais
