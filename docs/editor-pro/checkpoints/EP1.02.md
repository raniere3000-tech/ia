# EP1.02 — Integração do guia aprovado

Status: APROVADA para catálogo e roteador. Uso em produção do A5 será conectado em EP3.01.

Adicionado `short-form-retention` ao manifesto e ao perfil `editor.planejar_cortes`, com gatilho de corte vertical e fallback para os modelos existentes. Mantidos os 133 itens anteriores. O arquivo MIT tem commit e hash fixados. Scripts e referências do fornecedor ficam fora.

- `teste_skills_agentes.py`: 27 verificações, zero falhas, incluindo formato vertical, formato horizontal e guia desativado.
- `teste_skills.py`: 57 verificações, zero falhas.
- Validação isolada com os bytes reais extraídos do Git: instalação com hash conferido, 7 regras autorizadas e orientação carregada pelo roteador. Não houve registro de uso em render.
- Baseline complementar da etapa EP0.03: pipeline 51 e esteira 7 com 70 verificações, zero falhas em ambos.

Rollback: reverter o commit da etapa. O perfil novo sai do roteador e a entrada sai do manifesto, sem apagar registros históricos. Retomada: EP1.03, aproveitar o registry atual com sondagem de pré-requisitos do FFmpeg.
