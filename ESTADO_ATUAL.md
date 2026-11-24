# CHECKPOINT — EstúdioClip 2.0

Atualizado: 2026-11-24T14:04:45-03:00. Executor: Codex.

```yaml
fase: F1
microetapa: F1.04
status: COMMITTED
branch: claude/project-thread-hqyqog-fase1
sha_inicial: 299fd52be73f14e615b2ccf9a350636b3e1f3c61
sha_final_implementacao: 1b0483b6ff3a0928ac3d5dd79029af3e095ee2f7
proxima_microetapa: F1.05
mudancas_nao_commitadas: []
flags_adicionadas: []
migracoes: []
merge: NAO_REALIZADO
producao: NAO_PUBLICADA
sincronizacao_remota: SINCRONIZADA_NA_BRANCH_DE_TRABALHO
suite_completa: RESERVADA_A_F1_09
```

O SHA acima identifica implementação/testes. Checkpoint e logs seguem em commit
documental posterior; consultar git rev-parse HEAD para o HEAD final. Cada árvore
local/remota é comparada antes de sincronizar. Histórico local original preservado
em branches de segurança. Sem diffs pendentes após sincronização.

## Autorização persistente

O usuário autorizou seguir e fazer todas as fases em 24/11/2026. Executar várias
microetapas sequenciais por sessão está autorizado, mantendo teste e checkpoint
por microetapa e respeitando limites de uso. Isso substitui a restrição dos cartões
de uma única microetapa por sessão. Commits e envio à branch de trabalho automáticos.
Merge e publicação em produção continuam sem autorização. Não pedir novamente
permissão para continuar etapas autorizadas ou sincronizar esta branch.

## Última microetapa

Adaptador fila.estado_publico acrescenta estado_comum, heartbeat_atrasado e estado_motivo sem alterar status persistido. Fila e consulta individual expõem CREATED/QUEUED/RUNNING/WAITING_USER/PAUSED/RETRYABLE_ERROR/CANCEL_REQUESTED/CANCELLED/FAILED/COMPLETED. Heartbeat ausente/vencido ou lease vencida não é RUNNING e não recebe ETA de execução. Coordenador/painel separam jobs recuperáveis dos ativos. UI de fila e painel de agentes consomem sinal de leitura; dados legados continuam suportados. Sem colunas novas. Testes: teste_estados_fila.py 3 testes (mapeamento, precedência, lease, API, lista, painel sem escrita e subprocesso de reinício), teste_painel.py 34 verificações, teste_esteira_7.py 70 verificações; todos exit 0. Frontend npx tsc --noEmit exit 0 e npm test 16/16. git diff --check aprovado. Arquivos: fila.py, api_v1.py, coordenador.py, painel.py, teste_estados_fila.py e três consumidores frontend.

Evidências: docs/estudioclip-2/checkpoints/F1.04-*.
Último resultado: testes focais e git diff --check aprovados.

## Ponto exato de retomada — F1.05

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -3 --oneline
git fetch origin claude/project-thread-hqyqog-fase1
git rev-list --left-right --count HEAD...origin/claude/project-thread-hqyqog-fase1
cat ESTADO_ATUAL.md
```

Ler docs/estudioclip-2/microetapas/07_F1_05_REPETIR_FONTE_A1.md. Inventariar agente.rodar, fila A1 e _marcar_visto; testar repetição persistente da mesma fonte atrás de A1_MESMA_FONTE=0. Não refazer F1.04.

Não refazer Fase 0 ou microetapas concluídas. Relatórios anteriores permanecem em
checkpoints/. Flags desligadas por padrão. Rollback: git revert 1b0483b6ff3a0928ac3d5dd79029af3e095ee2f7
(não executar automaticamente). Sem migrações ou publicação em conta real.
Suite integral/frontend no fechamento F1.09; teste_agente3 integral ainda tem cenários
antigos pendentes de avaliação, embora o recorte F1.01 de render real passou 18/18.
Termux e APIs externas não verificados. Não afirmar aprovação integral da fase.
