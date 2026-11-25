# EP2.01 — Contrato de timeline versionado

Status: APROVADA para a primeira evolução de contrato, com uma fonte principal e trechos em ordem.

A timeline v2 valida revisão, listas limitadas, intervalos em ordem sem sobreposição, travas de duração positiva e um intervalo opcional de gancho contido no primeiro trecho. Correções respeitam as travas e o gancho. A versão 1 continua com a representação serializada e SHA originais. Trilhas múltiplas, máscaras e keyframes ainda serão tratadas nas etapas dos respectivos executores.

- `teste_editor_timeline.py`: 3/3. Hash v1, correções preservando gancho, versão e trava, além de listas, caminhos e intervalos inválidos.
- `teste_pipeline_5_agentes.py`: 51 verificações, zero falhas, com render do corte e certificado por arquivo.
- Rollback: desativar as funcionalidades novas antes de reverter o contrato. Não reinterpretar planos v2 persistidos como v1.
- Retomada: EP2.02, montagem silenciosa, ritmo e proteção da abertura no fluxo A1.
