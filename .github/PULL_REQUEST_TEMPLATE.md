## 📝 Descrição

<!-- Descreva clara e objetivamente as mudanças deste PR -->

## 🔗 Issue Relacionada

<!-- Link para issue(s) que este PR resolve -->
Closes #<!-- número da issue -->

## 🏷️ Tipo de Mudança

<!-- Marque a(s) opção(ões) aplicável(eis) -->

- [ ] 🐛 **Bug fix** (correção de bug existente)
- [ ] ✨ **Feature** (nova funcionalidade)
- [ ] 📚 **Documentação** (apenas docs)
- [ ] 🎨 **Style** (formatação, sem mudança lógica)
- [ ] ♻️ **Refactor** (refatoração de código)
- [ ] ⚡ **Performance** (melhoria de performance)
- [ ] ✅ **Test** (adicionar/corrigir testes)
- [ ] 🔧 **Chore** (manutenção, deps, config)
- [ ] 🚨 **Breaking Change** (mudança que quebra compatibilidade)

## ✅ Checklist de Validação

### Testes

- [ ] Testes unitários adicionados/atualizados
- [ ] Testes de integração adicionados/atualizados (se aplicável)
- [ ] Todos os testes passando localmente
- [ ] Coverage não diminuiu

### Código

- [ ] Código segue padrões do projeto (linter passing)
- [ ] Code review auto-crítico realizado
- [ ] Sem código comentado desnecessário
- [ ] Sem `console.log`, `print` ou debug statements
- [ ] Sem TODOs ou FIXMEs não documentados

### Documentação

- [ ] README atualizado (se necessário)
- [ ] Documentação técnica atualizada (se necessário)
- [ ] Comentários inline para lógica complexa
- [ ] Changelog atualizado (se projeto usa)

### Git

- [ ] Branch atualizada com `main`
- [ ] Sem conflitos de merge
- [ ] Commits seguem Conventional Commits
- [ ] Histórico de commits limpo (squash se necessário)

### Segurança

- [ ] Sem credenciais ou secrets commitados
- [ ] Dependências atualizadas e sem vulnerabilidades conhecidas
- [ ] Input validation apropriada (se aplicável)
- [ ] Autenticação/autorização preservada (se aplicável)

## 📸 Screenshots (se aplicável)

<!-- Para mudanças de UI, adicione antes/depois -->

### Antes

<!-- Screenshot do estado anterior -->

### Depois

<!-- Screenshot do novo estado -->

## 🧪 Como Testar

<!-- Descreva passos para testar as mudanças -->

1. Clonar branch: `git checkout {{ branch_name }}`
2. Instalar deps: `...`
3. Executar: `...`
4. Validar: `...`

## 🔄 Plano de Rollback (para mudanças críticas)

<!-- Apenas para mudanças em produção, infraestrutura ou dados -->

<!-- Descomente e preencha se aplicável:

### Como Reverter

1. Step 1
2. Step 2

### Responsáveis

- Tech lead: @username
- On-call: @username

### Contatos de Emergência

- Slack: #channel
- Email: team@example.com

-->

## 💭 Contexto Adicional

<!-- Informações extras, decisões técnicas, trade-offs, alternativas consideradas, etc. -->

## 📊 Impacto Estimado

<!-- Marque todas que se aplicam -->

- [ ] Baixo (mudança isolada, sem dependências)
- [ ] Médio (afeta alguns componentes)
- [ ] Alto (mudança arquitetural ou breaking change)

## 🏃 Performance

<!-- Apenas se houver impacto -->

<!-- Descomente e preencha se aplicável:

- Tempo de execução: antes X ms → depois Y ms
- Memória: antes X MB → depois Y MB
- Queries: reduzidas de X para Y
- Benchmark: link para resultados

-->

## 🔐 Segurança

<!-- Apenas se houver impacto -->

<!-- Descomente e preencha se aplicável:

- [ ] Revisado por security team
- [ ] Scan de vulnerabilidades executado
- [ ] Sem exposição de dados sensíveis
- [ ] Autenticação/autorização validada

-->

---

## 👥 Reviewers

<!-- @mention pessoas específicas se necessário -->

<!-- Sugestão de reviewers por área:
- Backend: @backend-team
- Frontend: @frontend-team
- DevOps: @devops-team
- Security: @security-team
-->

---

## 📋 Checklist Final do Autor

Antes de marcar como "Ready for Review":

- [ ] Li o CONTRIBUTING.md e segui as diretrizes
- [ ] Testei localmente todas as mudanças
- [ ] PR tem tamanho razoável (< 500 linhas idealmente)
- [ ] Descrição está clara e completa
- [ ] Todos os checkboxes relevantes marcados
- [ ] CI está passing
- [ ] Branch está atualizada com `main`

---

<!--
DICAS:

✅ Boas práticas:
- Descrever O QUE mudou e POR QUÊ
- Screenshots para mudanças visuais
- Link para documentação externa se relevante
- Mencionar breaking changes explicitamente
- Adicionar GIFs para interações complexas

❌ Evitar:
- Descrições vagas ("fix bug", "update code")
- PRs gigantes (> 1000 linhas)
- Misturar múltiplos tipos de mudança
- Deixar checkboxes em branco sem justificativa
-->
