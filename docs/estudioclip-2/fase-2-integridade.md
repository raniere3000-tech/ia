# F2.03 — Integridade do render

`RENDER_INTEGRIDADE=0` por padrão. Com `1`, a conferência existente reprova
codec diferente de H.264/AAC, dessincronia de duração acima de 0,5s ou início
acima de 0,2s, preto detectado por pelo menos 1s, congelamento por pelo menos
4s, silêncio de pelo menos 3s e pico acima de -0,1 dB. Uma análise que falha
não libera o arquivo. São sinais técnicos, não avaliação estética ou de fala.

O manifesto manual informa intervalos de imagens intencionalmente paradas;
o editor informa intervalos de B-roll de imagem. A exceção vale somente nos
intervalos previstos, com tolerância de 0,2s. Exportação pedida sem áudio
informa silêncio intencional. Outras exceções exigem dados explícitos do
chamador; nenhuma regra deduz que todo congelamento é intencional.

A conferência sempre registra métricas reais de volume médio/pico (dB),
diferença entre as durações e inícios de áudio/vídeo e intervalos detectados.
Ausência de medição é `null`, nunca volume fictício. O editor só liga essa
conferência estrita no executor `A5_EFEITOS_REAIS=1`; ambos desligados por padrão.

A exportação valida `final.tmp.mp4` antes de trocar `final.mp4`. O executor
de efeitos também valida o temporário e guarda o recibo de falha antes de
propagar o erro. Cancelamento é conferido antes da troca. A fila manual já
limita as tentativas a duas; essa política foi preservada e testada.

Corrigida a ordem trim/tpad/setpts que truncava a cauda de transição no
FFmpeg 7. Cache dos segmentos avança para versão 3. O processo FFmpeg é
recolhido e seus pipes são fechados também depois de timeout/cancelamento.

A falha histórica de `teste_exportacao.py` registrada em F1.09 foi resolvida:
23 verificações aprovadas. O resultado original da suíte F1 permanece no
relatório histórico; não representa aprovação global do projeto. Termux e
APIs de contas reais não foram executados neste ambiente.
