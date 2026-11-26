# Inventário: o que já existe e o que falta confirmar

## Evidência da passagem Fase 0 / Fase 1
- `fila.py`: fila persistente, lease/heartbeat, tentativas, chaves idempotentes, cancelar, pausar, retomar.
- `produtor.py`: limite de reprovações introduzido no patch, porém o teste `teste_agente3` ainda reprova depois de aprovação de roteiro.
- `aprovacoes.py`: liberação de job que está rodando alterada no patch; corrida de escrita/estado permanece suspeita.
- `editor_ia.py`: motor de plano de edição `EditPlan`, filtros FFmpeg e checagem pelo Diretor já estão presentes. Melhorar execução real **sem duplicar motor**.
- `aprendizado.py`: snapshots de métricas, amostra mínima, experimentos e pesos versionados já existem. Não criar outro sistema paralelo de memória de performance.
- `inteligencia_viral.py`: referências com números medidos, cache e amostra mínima já existem.
- `agenda_postagem.py`: agendamento independente por rede, slots idempotentes e regras de atraso.
- `frontend/src/navigation/rotas.ts`: cinco áreas já existem, rotas legadas suportadas. Não reescrever o roteador.
- `servidor/testes/`: testes existentes para agente 3, esteira, diretor, aprendizado, postagem, editor, thumbs, cancelamentos e regressões.

## Já modificado, mas incompleto
- `produtor.py`: contador `MAX_REPROVACOES_ETAPA`, espera após exceder limite, bypass após aprovação do usuário.
- `fila.py`: marca aprovação recebida enquanto o job ainda roda (`liberar:<jid>`).
- `aprovacoes.py`: libera jobs `agente3.produzir` rodando ou esperando.
- O patch **não é um conserto comprovado**: teste do Agente 3 ainda falha no ponto de continuação.

## Itens com escopo reduzido
- F1: terminar correção, estados e controles de tarefas com testes; não redesenhar todo o fluxo.
- F2: fortalecer A1 + A5 usando `agente.py`, `editor_ia.py`, `pipeline.py`, `renderizador.py`, `visual_presets.py` e telas existentes.
- F3: fortalecer A3 com `produtor.py`, `criativo.py`, `storyboard.py`, `series.py`, `renderizador.py`.
- F4: métricas e pendências em `postagem.py`, `agenda_postagem.py`, `aprendizado.py`, `painel.py`; fazer antes inventário das APIs/contas e do que a API realmente devolve.
- F5: mostrar analytics e distribuir orientações usando `aprendizado.py`, `inteligencia_viral.py`, `coordenador.py`, frontend existente. Só adicionar nova aba se não couber de modo claro na área atual.

## Cuidados de escopo
- Não presumir que documento significa código implementado; verificar função, rota, teste e evidência real.
- Não substituir testes que detectam bloqueios reais apenas para torná-los verdes.
- Não importar automaticamente estratégia do e-book de alteração de metadados/espelhamento como método para driblar originalidade.
- Não testar publicações com contas reais sem aprovação explícita; não executar teste contra `~/.estudioclip` real.
