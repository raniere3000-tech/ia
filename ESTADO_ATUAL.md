# CHECKPOINT — EstúdioClip 2.0

Atualizado: 2026-11-24T19:04:35-03:00.

```yaml
fase: F3
microetapa: F3.01
status: COMMITTED
branch: codex/estudioclip-2-fase3
sha_inicial: 36d9828d8a88687dad3dfff3cd5d385a5ca05aec
sha_final_implementacao: 285094e3082afa801cda27612fd2ed483473012e
proxima_microetapa: F3.02
mudancas_nao_commitadas: []
teste_focal: 23_PASS
aprovacao_concorrente: 10_PASS
teste_agente3_integral: BLOCKED_130_PASS_8_FAIL_EXCECAO
flags_adicionadas: []
migracoes: []
merge: NAO_REALIZADO
producao: NAO_PUBLICADA
```

O SHA identifica implementação/testes; checkpoint/logs em commit documental
posterior. Conferir HEAD para o SHA final. Árvores local/remota comparadas
antes de alinhar; commits locais originais preservados em seguranca/.

## Autorização persistente

O usuário autorizou todas as fases e commits/envio automáticos em 24/11/2026.
Prosseguir microetapas sequenciais, cada uma testada, commitada e com checkpoint.
Não refazer Fase 0 ou partes concluídas. Não fazer merge ou deploy.

## Estado real

F1 no PR #21, F2 no PR #22, ambos em rascunho. F2.01–F2.04 testadas e
commitadas. Flags novas desligadas por padrão. Falhas históricas de estilos
zerados e exportação foram corrigidas e testadas na F2.

F3.01 valida criar/revisar/aprovar roteiro, recusar versão antiga e continuar
no mesmo job até render real com SHA e sem post: 23 verificações aprovadas.
Não houve alteração em módulos do aplicativo nem reaplicação da F1.01.
Integral continua bloqueado; ler docs/estudioclip-2/fase-3-roteiro.md e
checkpoints/F3.01-agente3-retomada.log. Duas causas observadas: aviso de
biblioteca mais nova bloqueia snapshot antigo preservado; opinião da visão
bloqueia a etapa final. Não afirmar aceite integral da Fase 3.

## Retomada exata — F3.02

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git fetch origin codex/estudioclip-2-fase3:refs/remotes/origin/codex/estudioclip-2-fase3
git rev-list --left-right --count HEAD...origin/codex/estudioclip-2-fase3
cat docs/estudioclip-2/microetapas/13_F3_CRIACAO_IA_INCREMENTAL.md
```

Verificar snapshots existentes em series.py/criativo.py e a conferência em
produtor.continuidade_serie. Testar duas cenas e duas versões de personagem,
voz, estética e cenário; preservar snapshot do episódio, sem adotar a
aparência mais recente silenciosamente. Corrigir somente bloqueio informativo
com evidência de snapshot preservado; voz errada/personagem/cenário inválidos
continuam bloqueados. Separar simulador negativo de continuidade dos casos
positivos; não falsificar aprovação do Diretor.

F3.03: compartilhamento A5/A4 e política de opinião visual versus defeitos
objetivos. F3.04: presets editáveis. F4.02: teste_reposicao ainda pendente.
Termux, email e APIs reais não validados. Sem migrações ou produção.
Rollback se solicitado: git revert 285094e3082afa801cda27612fd2ed483473012e.
