# EP2.05 — Áudio e design sonoro

Status: PARCIAL. Cadeia de redução de ruído, EQ e compressão implementada. Mixagem com temporização e ducking executada. A separação de voz/música, a escolha autônoma de efeitos e as provas isoladas de cada categoria sonora permanecem abertas.

O Editor Pro aceita camadas sonoras tipadas e com autorização de uso, conferindo SHA-256 do asset, ganho, duração, início e formato. O efeito de ducking é aplicado quando há áudio de referência. Sem áudio de origem, a trilha continua disponível com o motivo registrado. Filtros ausentes geram fallback. Arquivos entram em argumentos de processo e filtros são montados pelo código.

- `teste_efeitos_reais.py`: 12/12 em 14,906 s. Foram medidos sinal de 760 Hz depois de 500 ms, atenuação durante voz e recuperação após a fala. A cadeia de processamento alterou a intensidade de 440 Hz. O teste verifica SHA do asset e MP4, e recusa mídia sem autorização.
- Rollback: deixar de gerar os efeitos `audio` e `som` em planos novos. Preservar planos e recibos existentes.
- Próxima frente independente: EP2.06, VFX e composição.
