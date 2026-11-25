# F1.06 — Cancelar, ignorar e retomar sem perder auditoria

**Situação inicial:** PENDENTE. **Escopo máximo:** 15–35 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/fila.py`, `servidor/aprovacoes.py`, rotas e telas de fila/revisar.

## Execução cirúrgica
1. Reaproveitar `fila.cancelar`, `pausar`, `retomar`, `ignorar`; validar em fila, IA, render, QA e `WAITING_USER`.
2. Corrigir somente estágios sem cancelamento cooperativo; garantir que ação cancelar não vire concluir após corrida.
3. Ignorar/rejeitar remove da lista de pendências visível, mas preserva registro de decisão.
4. No reinício, tarefas canceladas não devem renascer; tarefas pausadas não devem iniciar sozinhas.
5. Testes com base temporária, subprocesso de render falso e reinício; nunca conta real.

## Testes focais
Testes `teste_painel.py`, `teste_esteira_7.py`, `teste_versao_refeita.py` + novos testes focais para WAITING_USER/cancelamento.

## Aceite / checkpoint
Ações no estágio correto, sem itens fantasmas ou tarefas retomadas indevidamente.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
