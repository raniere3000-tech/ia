# EP2.02 — Montagem, ritmo e gancho

Status: PARCIAL. Montagem ordenada, mudança de velocidade por trecho e proteção de gancho executadas. Permanecem J/L cuts, match cuts, montagem paralela, emoção e continuidade dirigidas pelo A5, congelamento, corte por batida, pattern interrupt e rampa contínua.

A montagem compartilhada entre cortes e importados passou a usar tempo por trecho, `setpts` e `atempo`. Os timestamps da transcrição e o mapa inverso para o Diretor acompanham a velocidade. A montagem com fade aceita mídia sem trilha de áudio. O A3 continua guardando a duração das cenas e recusa mudanças de velocidade no acabamento compartilhado. O A1 usa a proteção do gancho e dispensa legenda sem transcrição quando `A5_EDITOR_PRO=1` e `A5_EFEITOS_REAIS=1`. A flag Pro fica desligada por padrão.

- `teste_efeitos_reais.py`: 8/8 em 9,253 s. Mídia sintética com trechos a 0,5× e 2×, diferença de pixels, trilhas dentro de 100 ms, decodificação integral, abertura preservada, áudio ausente e recibo vinculado ao SHA.
- `teste_editor_timeline.py`: 3/3. `teste_pipeline_5_agentes.py`: 51 verificações. `teste_a3_editor_compartilhado.py`: 9/9. Zero falhas.
- Reversão: manter `A5_EDITOR_PRO=0` para novas tarefas; concluir ou reavaliar as que já têm planos v2 antes de reverter o motor.
- Retomada da montagem avançada: modelar áudio e imagem em trilhas independentes antes de J/L cuts. Próximo trabalho independente na sequência: EP2.03, proteger região de interesse no reenquadramento.
