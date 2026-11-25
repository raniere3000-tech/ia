# Protocolo resistente a limite de uso

## Contrato para Claude/Codex — SEM EXCEÇÕES
A unidade de execução é **uma microetapa, com um teste verificável e um checkpoint**. Não começar tarefa longa que não caiba no contexto/cota disponível. Se perceber limite próximo, registrar a execução e parar. Nenhum progresso deve depender só da conversa.

### Início de cada sessão
1. Verificar branch atual, `git status --short`, `git rev-parse HEAD`, commits recentes e se há trabalho não commitado.
2. Abrir `ESTADO_ATUAL.md` no repositório. Se não existir, copiar o modelo deste pacote. Ler o último relatório de execução em `docs/estudioclip-2/checkpoints/`.
3. Confirmar que não houve alteração remota concorrente. **Nunca resetar, sobrescrever ou aplicar patch em cima de uma edição existente sem comparar.**
4. Executar apenas o teste focal que reproduz o defeito; guardar saída e tempo.

### Durante
- Preferir correção de 1 causa por vez. Preservar contratos públicos e dados legados.
- Para alterações de comportamento, flag desativada por padrão. Correção de defeito pode ser direta com regressão focal.
- Se uma migração for indispensável, somente aditiva, com backup verificado e teste de migração em banco temporário.
- Cada execução deve ser determinística e tolerar reinício quando pertinente.

### Encerramento obrigatório (mesmo parcial)
Atualizar `ESTADO_ATUAL.md` com: fase/microetapa, status `NOT_STARTED | IN_PROGRESS | BLOCKED | TESTED | COMMITTED`, branch, SHA inicial e final, arquivos tocados, comportamento antes/depois, último comando/teste/resultado, falhas, mudanças não commitadas, próxima ação exata, flags, rollback e pendências externas. Se houver diffs não commitados, salvar arquivo patch e listar os caminhos; nunca dizer que tudo está salvo apenas porque o chat foi atualizado.

**Critério de microetapa finalizada:** alterações em commit identificável + teste focal aprovado + checkpoint atualizado + nenhuma regressão nova relevante detectada. Caso falte um desses, permanecer `IN_PROGRESS`/`BLOCKED`.

### Comandos de retomada (exemplos)
```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -3 --oneline
git diff --stat
cd servidor && PYTHONPATH=. python3 testes/teste_agente3.py
```
No encerramento da fase, executar suite completa e frontend em ambiente isolado. Não repetir a suite toda após cada microetapa.

### Política de tempo
Estimativa de trabalho **indicativa**, não compromisso: microetapa focal 15–40 min de engenharia + 2–10 min de teste; validação integral da fase pode acrescentar 15–40 min dependendo do ambiente. Se a correção ultrapassar a janela, dividir novamente e registrar checkpoint.
