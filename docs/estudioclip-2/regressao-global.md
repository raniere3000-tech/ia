# Regressão global — EstúdioClip 2.0

Código validado: f987561958838f6194ca245e3383a122f4e3a011 (F5.04). Árvore limpa durante toda a rodada.

**70 arquivos catalogados: 69 PASS, zero FAIL, um diagnóstico interativo não executado.** Nenhum timeout. Tempo somado: 723.8 s.

O diagnóstico teste_email.py pede credenciais e envia email real: fica manual. yt-dlp 2026.11.23 foi instalado somente neste ambiente; teste_trecho_link passou com downloader simulado. Nenhuma conta real usada.

As quatro falhas históricas da F1.09 passaram nesta rodada: agente3 (176 verificações), estilos_visuais (65), exportacao (23), reposicao (35). Frontend da F5.04: 18 testes e TypeScript/Vite passaram.

Logs, resultados JSON e runner em checkpoints/REGRESSAO_FINAL-suite. O runner registra saída/tempo por arquivo, com timeout de 1200 s; para reproduzir, ajustar repo no início do arquivo ao caminho local.

Próxima tarefa F5.R01: ajustes de compatibilidade encontrados na revisão (flag F5 desligada, data de medição antiga ausente, perfil de publicação separado do canal fonte e metadados por render arquivado). Serão validados por testes complementares, sem apresentar esta rodada como execução posterior a esses ajustes.

| Arquivo | Resultado | Exit | Segundos |
| --- | --- | --- | --- |
| teste_3d.py | PASS | 0 | 2.48 |
| teste_a3_editor_compartilhado.py | PASS | 0 | 12.76 |
| teste_aceite_linha6.py | PASS | 0 | 63.65 |
| teste_agenda_agente2.py | PASS | 0 | 3.16 |
| teste_agente3.py | PASS | 0 | 127.42 |
| teste_alertas.py | PASS | 0 | 0.27 |
| teste_aprendizado.py | PASS | 0 | 0.11 |
| teste_aprovacao_roteiro_corrida.py | PASS | 0 | 0.22 |
| teste_busca_canais.py | PASS | 0 | 0.06 |
| teste_cancelamento.py | PASS | 0 | 0.27 |
| teste_central_automacao.py | PASS | 0 | 6.05 |
| teste_comandos.py | PASS | 0 | 0.17 |
| teste_comparacao.py | PASS | 0 | 7.65 |
| teste_consistencia_projeto.py | PASS | 0 | 5.64 |
| teste_coordenador.py | PASS | 0 | 9.4 |
| teste_criativo.py | PASS | 0 | 1.17 |
| teste_custo_corte.py | PASS | 0 | 16.75 |
| teste_decisoes.py | PASS | 0 | 0.17 |
| teste_descricao.py | PASS | 0 | 0.27 |
| teste_diretor.py | PASS | 0 | 0.22 |
| teste_dna_corte.py | PASS | 0 | 1.37 |
| teste_efeitos_reais.py | PASS | 0 | 5.31 |
| teste_email.py | INTERATIVO_CONTA_REAL | None | 0 |
| teste_estados_fila.py | PASS | 0 | 0.22 |
| teste_esteira_7.py | PASS | 0 | 29.73 |
| teste_esteira_corte_salvo.py | PASS | 0 | 0.06 |
| teste_estilos_agente1.py | PASS | 0 | 0.11 |
| teste_estilos_editar.py | PASS | 0 | 87.03 |
| teste_estilos_visuais.py | PASS | 0 | 8.6 |
| teste_exportacao.py | PASS | 0 | 19.12 |
| teste_feedback_metricas.py | PASS | 0 | 0.11 |
| teste_ffmpeg_tempo.py | PASS | 0 | 16.32 |
| teste_formatos_ia.py | PASS | 0 | 0.22 |
| teste_gameplay.py | PASS | 0 | 42.22 |
| teste_gancho_capa.py | PASS | 0 | 1.32 |
| teste_gancho_integro.py | PASS | 0 | 0.11 |
| teste_historico_publicacao.py | PASS | 0 | 0.11 |
| teste_idempotencia_fila_capa.py | PASS | 0 | 0.11 |
| teste_indicadores.py | PASS | 0 | 0.11 |
| teste_integridade_render.py | PASS | 0 | 7.79 |
| teste_kwai_diario.py | PASS | 0 | 0.06 |
| teste_liberacao.py | PASS | 0 | 0.92 |
| teste_liberar_corte.py | PASS | 0 | 0.17 |
| teste_link_original.py | PASS | 0 | 0.06 |
| teste_live.py | PASS | 0 | 34.81 |
| teste_memoria_metricas.py | PASS | 0 | 0.11 |
| teste_metricas_publicacoes.py | PASS | 0 | 0.11 |
| teste_motor.py | PASS | 0 | 41.18 |
| teste_pacote.py | PASS | 0 | 4.49 |
| teste_painel.py | PASS | 0 | 0.67 |
| teste_perfis.py | PASS | 0 | 20.97 |
| teste_pipeline_5_agentes.py | PASS | 0 | 11.35 |
| teste_portao_diretor.py | PASS | 0 | 0.17 |
| teste_publicacao_lotes.py | PASS | 0 | 1.17 |
| teste_ranking_metricas.py | PASS | 0 | 0.11 |
| teste_redes_independentes.py | PASS | 0 | 0.41 |
| teste_rejeitar_thumbnail.py | PASS | 0 | 0.22 |
| teste_reposicao.py | PASS | 0 | 1.33 |
| teste_retry_fonte_a1.py | PASS | 0 | 0.16 |
| teste_serie_completa.py | PASS | 0 | 0.22 |
| teste_site_lote1.py | PASS | 0 | 3.43 |
| teste_skills.py | PASS | 0 | 0.17 |
| teste_skills_agentes.py | PASS | 0 | 1.97 |
| teste_skills_novas.py | PASS | 0 | 84.25 |
| teste_temas.py | PASS | 0 | 0.11 |
| teste_thumbnails.py | PASS | 0 | 20.24 |
| teste_tiktok_assistido.py | PASS | 0 | 0.11 |
| teste_trecho_link.py | PASS | 0 | 0.27 |
| teste_versao_refeita.py | PASS | 0 | 0.51 |
| teste_whatsapp.py | PASS | 0 | 16.22 |

## Complemento posterior — F5.R01

A revisão indicada acima foi executada e testada: sete testes novos, onze grupos
Python afetados e frontend 18/build PASS. Detalhes em fase-5-compatibilidade.md e
checkpoints/F5.R01-*.log. O inventário agora tem 71 arquivos (70 automáticos e o
email interativo). Não somar repetições de testes como novos arquivos.
A rodada global de 69 arquivos continua vinculada ao SHA inicial registrado;
os testes complementares cobrem as mudanças posteriores.
