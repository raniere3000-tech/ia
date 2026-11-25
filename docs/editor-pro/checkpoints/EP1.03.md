# EP1.03 — Sondagem de dependências do editor

Status: APROVADA no Linux.

O registry existente inspeciona os filtros e os encoders do FFmpeg e a presença do ffprobe. Montagem A/V, zoom, legenda, loudnorm, B-roll e integridade agora têm diagnóstico por operação, versão, dependências ausentes e fallback descrito. A apresentação reaproveita a API e a tabela de capacidades. O resultado da sonda indica pré-requisitos e o recibo do render comprova execução.

Teste: `PYTHONPATH=servidor python servidor/testes/teste_editor_capacidades.py`, 2/2. Foram verificados falta simulada de filtros/encoder, dependências reais e persistência SQLite. Android físico: PENDENTE_TERMUX.

Rollback: reverter o commit desta etapa. Retomada: EP2.01, contrato retrocompatível de timeline.
