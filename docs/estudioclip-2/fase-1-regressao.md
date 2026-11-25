# EstúdioClip 2.0 — Fase 1: regressão e entrega para revisão

Branch: claude/project-thread-hqyqog-fase1. Base main observada: f388e22fe5c5518c421bd85e55a2be6606780f4c.
Estado: IMPLEMENTADA COM PENDÊNCIAS EXPLÍCITAS; não liberada para produção.
F1.01–F1.08 têm commits isolados, testes focais e checkpoint. Nenhuma fase anterior refeita.

## Resultado integral neste ambiente

57 arquivos catalogados: **51 PASS, 4 FAIL, 1 interativo, 1 dependente de ambiente**.
55 arquivos executados até terminar; nenhum timeout. Os seis arquivos novos passaram.
Frontend: TypeScript aprovado, 16 testes aprovados e build aprovado.
Logs integrais, stdout/stderr e tempos: checkpoints/F1.09-suite/ e F1.09-*.log.
Runner terminou normalmente; isso não significa que a suíte esteja toda aprovada.

O pacote informava 52 arquivos e baseline 43 PASS/7 FAIL/2 dependentes. O inventário
Git do SHA de continuidade ca26526 tem **51** arquivos teste_*.py. Não inventamos um
52º arquivo: este relatório usa a lista real e preserva a divergência do documento.

## Falhas e classificação

| Teste | Evidência atual | Classificação / encaminhamento |
| --- | --- | --- |
| teste_agente3.py integral | Primeiro projeto passa até revisão/render e aprovação final; cenário posterior supervisionado recebe revisão manual por gancho sempre reprovado pelo Gemini falso; após 400s fixture supõe imagens prontas e dá KeyError imagem | Fixture integral antiga ainda incompatível com política de QA. Não remover porta do Diretor. F1.01 validou o recorte real 18/18. Adaptar cenários de produção na F3.01 com aprovação explícita ou correção legítima |
| teste_estilos_visuais.py | industrial_impacto e retro_vhs com força zero diferem 5,40 do controle | Reproduzido no SHA inicial ca26526 com os mesmos números, exit 1. Não é regressão da F1. Investigar efeitos zerados em F2.02 |
| teste_exportacao.py | Duração de quadro com transição fica 2,00s em vez de 2,40s; teste termina em StopIteration | Reproduzido no SHA inicial ca26526, exit 1. Não é regressão da F1. Corrigir duração/render em F2.03 |
| teste_reposicao.py | 31 verificações aprovadas e duas falhas no caminho antigo sem agenda diária | Reproduzido no SHA inicial ca26526, mesmos dois cenários, exit 1. Investigar isolamento de estado/intervalo e reposição na F4.02 |
| teste_email.py | Pede e-mail pelo teclado | Interativo; não executado com conta real |
| teste_trecho_link.py | yt_dlp não instalado | Dependência de ambiente, já ressalvada no baseline |

As seis outras falhas iniciais (central, comandos, coordenador, descrição, liberação,
skills_agentes) passaram integralmente nesta execução. Não declarar o teste completo
do Agente 3 aprovado: o resultado dele continua FAIL, com a evidência acima.

## Mudanças, flags e rollback

Reutilizados fila, projetos, aprovações, produtor, postagem, coordenador, thumbnails,
painel e consumidores frontend. Sem serviço/agent/banco paralelo, sem alteração de
esquema ou migração. Flags novas **A1_MESMA_FONTE=0** e **THUMB_REJEICAO=0** por padrão;
limite A1_FONTE_MAX_TENTATIVAS=3 (1..10). Ver fase-1-flags.md.

Rollback: reverter os commits de implementação da microetapa necessária, pela branch
de trabalho, sem resetar dados. Hashes nos checkpoints F1.01–F1.08. Flags off não apagam
auditoria. Nenhum merge, deploy, publicação real ou teste em banco de produção.
Termux, consumo real com agentes simultâneos e contas externas continuam não verificados.

## Continuidade autorizada

O usuário autorizou todas as fases e commits automáticos, sem merge/produção. Abrir PR
**draft** da Fase 1 com essas ressalvas; melhorias seguintes seguem em branch empilhada,
sem misturar o PR da Fase 2 com este. Esta entrega não é aceite para produção; defeitos
preexistentes acima permanecem rastreados nas fases correspondentes. Não exigir nova
permissão para continuar implementação e testes já autorizados.

## Inventário executado

| Arquivo | Estado | Exit | Segundos |
| --- | --- | --- | --- |
| teste_3d.py | PASS | 0 | 2.69 |
| teste_aceite_linha6.py | PASS | 0 | 77.9 |
| teste_agenda_agente2.py | PASS | 0 | 4.22 |
| teste_agente3.py | FAIL | 1 | 412.03 |
| teste_alertas.py | PASS | 0 | 0.26 |
| teste_aprendizado.py | PASS | 0 | 0.16 |
| teste_aprovacao_roteiro_corrida.py | PASS | 0 | 0.27 |
| teste_busca_canais.py | PASS | 0 | 0.11 |
| teste_cancelamento.py | PASS | 0 | 0.32 |
| teste_central_automacao.py | PASS | 0 | 7.01 |
| teste_comandos.py | PASS | 0 | 0.22 |
| teste_comparacao.py | PASS | 0 | 12.05 |
| teste_coordenador.py | PASS | 0 | 10.39 |
| teste_criativo.py | PASS | 0 | 1.28 |
| teste_custo_corte.py | PASS | 0 | 19.98 |
| teste_decisoes.py | PASS | 0 | 0.17 |
| teste_descricao.py | PASS | 0 | 0.32 |
| teste_diretor.py | PASS | 0 | 0.27 |
| teste_email.py | NAO_AUTOMATICO | — | — |
| teste_estados_fila.py | PASS | 0 | 0.27 |
| teste_esteira_7.py | PASS | 0 | 34.4 |
| teste_esteira_corte_salvo.py | PASS | 0 | 0.12 |
| teste_estilos_agente1.py | PASS | 0 | 0.11 |
| teste_estilos_editar.py | PASS | 0 | 109.3 |
| teste_estilos_visuais.py | FAIL | 1 | 13.34 |
| teste_exportacao.py | FAIL | 1 | 7.62 |
| teste_ffmpeg_tempo.py | PASS | 0 | 16.28 |
| teste_gameplay.py | PASS | 0 | 56.46 |
| teste_gancho_capa.py | PASS | 0 | 1.32 |
| teste_idempotencia_fila_capa.py | PASS | 0 | 0.11 |
| teste_kwai_diario.py | PASS | 0 | 0.11 |
| teste_liberacao.py | PASS | 0 | 1.07 |
| teste_liberar_corte.py | PASS | 0 | 0.17 |
| teste_link_original.py | PASS | 0 | 0.06 |
| teste_live.py | PASS | 0 | 35.57 |
| teste_motor.py | PASS | 0 | 44.44 |
| teste_pacote.py | PASS | 0 | 5.45 |
| teste_painel.py | PASS | 0 | 0.78 |
| teste_perfis.py | PASS | 0 | 26.51 |
| teste_pipeline_5_agentes.py | PASS | 0 | 15.01 |
| teste_portao_diretor.py | PASS | 0 | 0.22 |
| teste_publicacao_lotes.py | PASS | 0 | 1.22 |
| teste_redes_independentes.py | PASS | 0 | 0.42 |
| teste_rejeitar_thumbnail.py | PASS | 0 | 0.27 |
| teste_reposicao.py | FAIL | 1 | 1.68 |
| teste_retry_fonte_a1.py | PASS | 0 | 0.22 |
| teste_serie_completa.py | PASS | 0 | 0.28 |
| teste_site_lote1.py | PASS | 0 | 4.2 |
| teste_skills.py | PASS | 0 | 0.12 |
| teste_skills_agentes.py | PASS | 0 | 2.08 |
| teste_skills_novas.py | PASS | 0 | 79.15 |
| teste_temas.py | PASS | 0 | 0.06 |
| teste_thumbnails.py | PASS | 0 | 18.67 |
| teste_tiktok_assistido.py | PASS | 0 | 0.12 |
| teste_trecho_link.py | AMBIENTE | — | — |
| teste_versao_refeita.py | PASS | 0 | 0.52 |
| teste_whatsapp.py | PASS | 0 | 16.27 |

## Atualização posterior — Fase 2

O registro da execução integral acima permanece histórico. Na F2.02, a força
zero dos estilos foi corrigida: teste_estilos_visuais passou com 65 verificações.
Na F2.03, a cauda da transição da exportação foi corrigida: teste_exportacao
passou com 23 verificações. Logs e SHAs nos respectivos checkpoints. As outras
duas falhas integrais (agente3 e reposicao) continuam encaminhadas a F3.01 e
F4.02. As limitações de email/yt_dlp e Termux permanecem explícitas.

## Atualização posterior — F3.03

`teste_agente3.py` integral passou: 176 verificações, zero falhas. As correções
de roteiro F1.01 foram preservadas. Snapshots foram corrigidos na F3.02 e os
simuladores positivos/negativos foram separados na F3.03, sem relaxar bloqueios
do Diretor. Evidência: checkpoints/F3.03-agente3-integral.log. O resultado F1.09
acima permanece histórico; teste_reposicao continua pendente de F4.02.

## Atualização posterior — F4.02

`teste_reposicao.py` passou com 35 verificações. As duas falhas antigas eram
um cenário que afirmava ter horário livre após preenchê-lo com k3; agora
confere o caso ocupado e cria uma vaga real antes de pedir reposição. Código
de produção preservado. Evidência antes/diagnóstico/depois nos checkpoints.
Os quatro testes que falharam na execução histórica F1.09 tiveram correções
e verificações posteriores; isso não substitui uma nova suíte global integral.
