# EP2.03 — Enquadramento e região de interesse

Status: PARCIAL. Região estática e fallback renderizados. Rastreamento facial/objeto ao longo do tempo, estabilização e multicâmera real permanecem em aberto.

A timeline v2 aceita uma região normalizada `x,y,w,h`. A montagem posiciona o recorte para manter a região inteira. Se ela não couber ou a geometria não for confiável, preserva a imagem inteira. Composição de gameplay/câmera existente tem prioridade. A confirmação de fallback fica no recibo com motivo, fora da contagem de efeitos aplicados. Zoom acima de 1 e múltiplas regiões concorrentes são recusados para preservar a região.

`teste_efeitos_reais.py`: 9/9 em 11,110 s, com prova por pixels de marca na borda preservada e fallback enquadrando a imagem toda. `teste_editor_timeline.py`: 3/3. `git diff --check`: sem erros. Termux segue pendente.

Rollback: retirar a seleção de ROI dos novos planos antes de reverter; preservar as revisões antigas com recibo. Próxima frente independente: EP2.04, cor e finalização.
