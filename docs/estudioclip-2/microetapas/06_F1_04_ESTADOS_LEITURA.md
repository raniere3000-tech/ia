# F1.04 — Estados comuns apenas como adaptador de leitura

**Situação inicial:** PENDENTE. **Escopo máximo:** 15–35 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/fila.py`, `servidor/banco.py`, `servidor/painel.py` e rota de consulta existente.

## Execução cirúrgica
1. Inventariar os estados reais `jobs.status`, flags `pausado`/`cancelar` e heartbeat.
2. Adicionar normalização SOMENTE NA RESPOSTA: CREATED/QUEUED/RUNNING/WAITING_USER/PAUSED/RETRYABLE_ERROR/CANCEL_REQUESTED/CANCELLED/FAILED/COMPLETED.
3. Heartbeat velho não pode parecer RUNNING; mostrar mensagem de tarefa recuperável/travada.
4. Não renomear status persistidos; não acrescentar colunas sem consumidor real. `source_id`/`video_version_id`/`stage`/`error_code` ficam adiadas se não forem necessárias nesta fase.
5. Testes com status legados, lease expirado e reinício.

## Testes focais
Usar teste de fila/painel existente e acrescentar teste focal de mapeamento. Rodar `teste_painel.py` e `teste_esteira_7.py` se afetados.

## Aceite / checkpoint
UI/API mostra trabalho ativo fielmente sem quebra de estados antigos; nenhum dado anterior sofre migração destrutiva.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
