# EP2.04 — Cor e finalização

Status: PARCIAL. Ajustes de exposição, temperatura, saturação e contraste, FPS, CRF e limite de bitrate renderizados. LUTs registradas e correspondência entre cenas permanecem abertas.

A timeline v2 valida ajuste de cor SDR por faixas e perfil de entrega explícito. O executor converte opções tipadas em filtros e argumentos FFmpeg, registra filtros ausentes e omite o tratamento em HDR sinalizado. O recibo registra parâmetros, codec, FPS e bitrate medidos. O limite de bitrate usa VBV do encoder; o bitrate lido é a média do stream.

- `teste_efeitos_reais.py`: 11/11, 13,093 s. Diferença de pixels e luminância em amostra de cor, H.264 a 25 fps, bitrate médio conferido e MP4 decodificado por inteiro; filtro ausente gera fallback.
- `teste_integridade_render.py`: 7/7. `teste_editor_timeline.py`: 3/3. `teste_editor_capacidades.py`: 2/2. Zero falhas.
- Reversão: não incluir `cor` ou `delivery` nos novos planos; manter capacidade de ler recibos já produzidos.
- Próxima frente independente: EP2.05, limpeza e mixagem de áudio.
