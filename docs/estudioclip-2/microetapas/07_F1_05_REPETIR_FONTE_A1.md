# F1.05 — A1 tenta a mesma fonte antes de mudar de vídeo

**Situação inicial:** PENDENTE. **Escopo máximo:** 15–35 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/agente.py`, `servidor/servidor.py`, teste focal de retry.

## Execução cirúrgica
1. Conferir `_marcar_visto` de fonte falhada e `max_tentativas=1` da passagem.
2. Flag `A1_MESMA_FONTE=0` por padrão. Quando ativa, classificar erro transitório (timeout, 429, instabilidade, FFmpeg temporário) vs definitivo (privado, URL inválida, sem direito).
3. Para transitórios: até N tentativas, atraso crescente e mesma fonte; registrar contador persistente. Definitivo: BLOCKED com motivo.
4. Respeitar cancelamento, limite de custo e restrições de fonte; não transformar vídeos sem legendas em inválidos.
5. Testar reinício entre tentativas e ausência de troca indevida de fonte.

## Testes focais
Testes `teste_busca_canais.py`, `teste_estilos_agente1.py` e novo teste específico de repetição, isolados.

## Aceite / checkpoint
A1 não abandona fonte por falha recuperável; não insiste infinitamente; flag desligada conserva comportamento anterior.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
