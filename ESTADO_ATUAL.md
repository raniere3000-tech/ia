# CHECKPOINT — EstúdioClip 2.0

Atualizado: 2026-11-24T14:15:28-03:00. Executor: Codex.

```yaml
fase: F1
microetapa: F1.07
status: COMMITTED
branch: claude/project-thread-hqyqog-fase1
sha_inicial: ea6a61317917270a1e128862529781564aa0136c
sha_final_implementacao: 1bfe5a64a56fa90467808e14a2aba395f19931bd
proxima_microetapa: F1.08
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

Fila.enfileirar consulta chave e insere o job na mesma transação, devolvendo repetido para concorrente sem IntegrityError. Criar thumbnail serializa pedido com chave por origem/ref/SHA/config, recupera ligação de fila se houver queda entre registros e não duplica evento. Refazer capa usa chave por pedido, vídeo, variante, versão, texto e job anterior: dois cliques não geram duas refações; nova ação após falha/versão diferente continua possível. Aprovação com chave de cliente reutilizada em outro render é isolada pelo projeto/SHA; não retorna posts antigos. Testes: teste_idempotencia_fila_capa.py 4/4 (inclui oito solicitações simultâneas na fila, duas em criar/refazer, cancelar/liberar), teste_portao_diretor.py 15/15 (duas aprovações simultâneas e chave entre renders), teste_thumbnails.py exit 0, teste_agente3.py --somente-aprovacao-roteiro 18/18 com FFmpeg real. Sem nova fila/migração/flags. Arquivos: fila.py, aprovacoes.py, thumbnails.py e dois testes.

Evidências: docs/estudioclip-2/checkpoints/F1.07-*.
Último resultado: testes focais e git diff --check aprovados.

## Ponto exato de retomada — F1.08

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -3 --oneline
git fetch origin claude/project-thread-hqyqog-fase1
git rev-list --left-right --count HEAD...origin/claude/project-thread-hqyqog-fase1
cat ESTADO_ATUAL.md
```

Ler docs/estudioclip-2/microetapas/10_F1_08_THUMB_REJEITAR.md. Verificar seleção/rejeição por video_sha e preservar capa já aprovada da versão atual. Não gerar capa automaticamente ao rejeitar.

Não refazer Fase 0 ou microetapas concluídas. Relatórios anteriores permanecem em
checkpoints/. Flags desligadas por padrão. Rollback: git revert 1bfe5a64a56fa90467808e14a2aba395f19931bd
(não executar automaticamente). Sem migrações ou publicação em conta real.
Suite integral/frontend no fechamento F1.09; teste_agente3 integral ainda tem cenários
antigos pendentes de avaliação, embora o recorte F1.01 de render real passou 18/18.
Termux e APIs externas não verificados. Não afirmar aprovação integral da fase.
