# EP0.02 — Inventário de skills e competências

Status: APROVADA. Inventário estático na base de EP0.01.

- `matriz-competencias.md`: 72 IDs, localização das implementações, testes existentes e lacunas.
- `inventario-skills.md`: 24 entradas associadas a editor entre 133 no manifesto, com origem, licença, hash e gatilho.
- A biblioteca atual tem roteamento para consulta no editor manual e para outros agentes. O A5 não tem consumidor de orientação automática identificado.
- Instalação e histórico de uso no Android: PENDENTE_TERMUX.
- Validação: parsing dos 72 IDs e 24 entradas, revisão dos pontos de execução e `git diff --check`. Provas locais de render em EP0.03.
- Reversão: reverter o commit documental correspondente.
- Retomada: EP0.03, executar baseline local com mídia sintética e medir renderizadores existentes.
