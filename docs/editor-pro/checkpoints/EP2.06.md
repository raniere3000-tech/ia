# EP2.06 — VFX e composição

Status: PARCIAL. Camadas, chroma key, máscara retangular, máscara externa e desfoque temporal comprovados. Rotoscopia automática e remoção de fundo sem chroma ou máscara preparada permanecem abertas.

A timeline v2 aceita camadas de imagem/vídeo e máscaras como assets registrados, limitados por ID, SHA, formato, intervalo, retângulo e autorização de uso. Receitas fechadas geram filtros de transparência, composição e desfoque. O executor verifica os filtros da compilação e registra fallback quando necessário. Máscaras preparadas podem entrar em vídeo com timestamps ou em imagem estática. O teste atual cobre a imagem estática.

- `teste_efeitos_reais.py`: 14/14 em 17,460 s. A camada vermelha aparece somente no intervalo escolhido, o fundo verde é removido e o fundo original fica visível. Máscara externa e retângulo conferidos por pixels. SHA da máscara e MP4 conferidos. Desfoque temporal alterou pixels no trecho ativo.
- `teste_editor_capacidades.py` 2/2 e `teste_editor_timeline.py` 3/3.
- Reversão: não gerar camadas v2 em planos novos. Manter compatibilidade para ler revisões antigas.
- Próxima frente independente: EP2.07, movimento interpolado e tipografia.
