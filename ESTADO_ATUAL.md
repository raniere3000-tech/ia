# CHECKPOINT — EstúdioClip 2.0

Atualizado: 2026-11-24T14:09:02-03:00. Executor: Codex.

```yaml
fase: F1
microetapa: F1.05
status: COMMITTED
branch: claude/project-thread-hqyqog-fase1
sha_inicial: 88a3fa0cbb57400660055e0dcc41b77e4ae57c27
sha_final_implementacao: 93e0a157cd23e606944c39ad6f9bc6656bee08a4
proxima_microetapa: F1.06
mudancas_nao_commitadas: []
flags_adicionadas: ['A1_MESMA_FONTE=0']
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

A1 reaproveita trabalhar_cortes, processar_video, fila.Esperar e kv existente. Flag A1_MESMA_FONTE desligada por padrão; quando ativa, fonte é salva antes do trabalho, falhas transitórias repetem o mesmo vídeo com backoff 60/180/540s e limite A1_FONTE_MAX_TENTATIVAS (padrão 3, máximo 10). Não marca visto no erro recuperável. Esperar usa o mesmo job sem consumir orçamento infinito de tentativas. Definitivos/limites de custo param com BLOCKED; canal anteriormente aprovado é revalidado antes de repetir. Cancelamento impede a execução e limpa a fonte pendente do job cancelado. Sucesso encerra a pendência mantendo registro por fonte. Sem legenda não é classificado como erro; segue processar_video existente. Testes: teste_retry_fonte_a1.py 8/8 (inclui processo novo após reinício, fila com max_tentativas=1, cancelamento, FFmpeg temporário, permissão revogada e flag off), teste_busca_canais.py 13/13, teste_estilos_agente1.py 6/6; todos exit 0. Arquivos: servidor/agente.py e teste_retry_fonte_a1.py. Todos dados temporários, sem contas reais. Retry de banco de trechos segue mecanismo custo_corte existente; não foi substituído.

Evidências: docs/estudioclip-2/checkpoints/F1.05-*.
Último resultado: testes focais e git diff --check aprovados.

## Ponto exato de retomada — F1.06

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -3 --oneline
git fetch origin claude/project-thread-hqyqog-fase1
git rev-list --left-right --count HEAD...origin/claude/project-thread-hqyqog-fase1
cat ESTADO_ATUAL.md
```

Ler docs/estudioclip-2/microetapas/08_F1_06_CANCELAR_IGNORAR.md. Reutilizar teste_cancelamento.py, fila.cancelar/ignorar/recuperar e rotas existentes; testar WAITING_USER, auditoria e reinício.

Não refazer Fase 0 ou microetapas concluídas. Relatórios anteriores permanecem em
checkpoints/. Flags desligadas por padrão. Rollback: git revert 93e0a157cd23e606944c39ad6f9bc6656bee08a4
(não executar automaticamente). Sem migrações ou publicação em conta real.
Suite integral/frontend no fechamento F1.09; teste_agente3 integral ainda tem cenários
antigos pendentes de avaliação, embora o recorte F1.01 de render real passou 18/18.
Termux e APIs externas não verificados. Não afirmar aprovação integral da fase.
