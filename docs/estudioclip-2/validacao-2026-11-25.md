# Validação dos recursos — 25/11/2026

Atualizado: 2026-11-25T00:49:35-03:00. **Aprovado nos testes automatizados. Validação no aparelho e com contas reais pendente.**

## Versão e escopo

Main observada e reconferida: `eb0662072e770f9e0e06d22167b4bcd7dc1cf2cb`. Os PRs #27 e #28 já estavam integrados antes desta sessão; a main contém as Fases 1–5, os 11 recursos no iniciador, download em lote e atualizar-termux.sh. O PR26 antigo está fechado e foi substituído pela integração consolidada #27. Não reabrimos nem refizemos essa integração.

Branch de revisão: `codex/validacao-recursos-20261125`. Única alteração de teste: `bdcac77c089d9bc19478d51534b47d001b0db090`. O SHA local da rodada é 3ef0d81 (mesma árvore Git do commit remoto de teste). O código da aplicação coincide com main; apenas a preparação de teste_reposicao.py foi corrigida. Não houve merge ou deploy nesta validação.

## Resultado

| Verificação | Resultado | Alcance |
| --- | --- | --- |
| Suíte Python completa | 72 arquivos PASS; zero FAIL; zero timeout | 73 catalogados, email interativo excluído |
| Frontend | 18 testes PASS | Rotas e filtros existentes |
| TypeScript e build Vite | PASS | Build local; alerta de tamanho de bundle sem erro |
| Iniciador Termux | 3 testes PASS; bash -n PASS | Cópia isolada, 11 recursos e rollback explícito |
| Atualizador Termux | 3 testes PASS; bash -n PASS | Origem Git local: atualiza, preserva override e recusa conflito sem descartar edição |
| Matriz com recursos ativos | 9 testes PASS | FFmpeg real, A3/A5/A4, efeitos e certificado por SHA; controles negativos desativam flags de propósito |
| API HTTP com recursos ativos | 6 testes PASS | Servidor local real, autenticação, filtros, zero/ausência e consultas sem publicação |
| Reposição em fusos diferentes | 35 verificações PASS em UTC, São Paulo e Auckland | Mesma reserva real em três fusos |

Rodada global: 757.7 segundos somados. teste_agente3.py passou com 176 verificações. A suíte já inclui ativação, ajustes finais e download em lote da main consolidada. Não somar testes repetidos ou complementares como novos arquivos da suíte.

## Falha reproduzida e corrigida no teste

Antes: UTC teve 34 verificações PASS e uma FAIL; São Paulo teve 35 PASS. A agenda diária trabalha com America/Sao_Paulo e o caminho legado com o fuso local. O cenário reutilizava a hora formatada da primeira agenda como se estivesse no mesmo fuso do processo, portanto nem sempre apontava a reserva ocupada que dizia testar.

O cenário agora obtém a hora local pelo timestamp da reserva real: `datetime.fromtimestamp(s1['quando_utc'])`. A lógica de produção do agendamento não precisou de alteração. Evidências antes/depois em VALIDACAO-reposicao-*.log; passou também na suíte global em UTC.

## Site publicado

Navegação básica verificada no navegador: Início, Agentes, Estúdio IA e Publicações abriram. Estúdio IA apresentou Criar com IA, Séries e personagens, Produção em lote e Biblioteca criativa. As áreas do servidor exibiram o aviso de conexão esperado neste navegador novo, sem pareamento. Isso não informa se o seu celular está ligado ou conectado em outro navegador.

Página verificada: https://raniere3000-tech.github.io/ia/#estudio-ia/inicio

Os testes visuais automatizados locais com Playwright não foram executados: o binário não estava instalado e o download oficial recebeu HTTP403 neste ambiente. Foi feita navegação pública pelo navegador disponível, sem conectar contas ou publicar. Não afirmar cobertura visual completa/responsiva ou fluxo conectado pelo site.

## Limites para o aceite no aparelho

- Não acessamos seu processo Termux: versão carregada, valores de flags do processo, memória, temperatura, desempenho e três agentes simultâneos ainda precisam de medição no celular.
- Não enviamos email real, vídeos ou chamadas a contas reais YouTube/TikTok/Instagram. Tokens, permissões efetivas e aprovação do app TikTok não foram confirmados.
- Testes de integrações usam serviços simulados e bancos temporários. Métricas ausentes continuam indisponíveis; ativação de flag não fornece uma API inexistente.
- O atualizador foi executado com Git real local e comandos do sistema simulados. Instalação de pacotes e túnel no Android não foram exercitados.

## Evidências e reprodução

Logs completos, JSON de resultados, contexto da execução e scripts complementares em `checkpoints/VALIDACAO_2026_11_25/`. Os scripts registram o caminho deste workspace: ajustar a raiz ao reproduzir em outro checkout. O diagnóstico teste_email.py é manual e foi excluído deliberadamente.

Próximo passo: conferir no aparelho a main atualizada e executar os fluxos com ambiente/dados de teste, antes de considerar confirmada a operação real. A correção de fixture e este relatório ficam em PR de revisão, sem merge automático.

## Inventário da suíte

| Arquivo | Estado | Exit | Segundos |
| --- | --- | --- | --- |
| teste_3d.py | PASS | 0 | 2.38 |
| teste_a3_editor_compartilhado.py | PASS | 0 | 12.47 |
| teste_aceite_linha6.py | PASS | 0 | 63.63 |
| teste_agenda_agente2.py | PASS | 0 | 3.19 |
| teste_agente3.py | PASS | 0 | 137.7 |
| teste_alertas.py | PASS | 0 | 0.21 |
| teste_aprendizado.py | PASS | 0 | 0.11 |
| teste_aprovacao_roteiro_corrida.py | PASS | 0 | 0.22 |
| teste_ativacao_termux.py | PASS | 0 | 0.27 |
| teste_busca_canais.py | PASS | 0 | 0.06 |
| teste_cancelamento.py | PASS | 0 | 0.22 |
| teste_central_automacao.py | PASS | 0 | 6.76 |
| teste_comandos.py | PASS | 0 | 0.27 |
| teste_comparacao.py | PASS | 0 | 8.51 |
| teste_compatibilidade_metricas.py | PASS | 0 | 0.11 |
| teste_consistencia_projeto.py | PASS | 0 | 5.85 |
| teste_coordenador.py | PASS | 0 | 9.46 |
| teste_criativo.py | PASS | 0 | 1.22 |
| teste_custo_corte.py | PASS | 0 | 16.76 |
| teste_decisoes.py | PASS | 0 | 0.12 |
| teste_descricao.py | PASS | 0 | 0.27 |
| teste_diretor.py | PASS | 0 | 0.22 |
| teste_dna_corte.py | PASS | 0 | 1.42 |
| teste_download_lote.py | PASS | 0 | 2.77 |
| teste_efeitos_reais.py | PASS | 0 | 5.19 |
| teste_email.py | INTERATIVO_CONTA_REAL | None | 0 |
| teste_estados_fila.py | PASS | 0 | 0.22 |
| teste_esteira_7.py | PASS | 0 | 34.02 |
| teste_esteira_corte_salvo.py | PASS | 0 | 0.06 |
| teste_estilos_agente1.py | PASS | 0 | 0.11 |
| teste_estilos_editar.py | PASS | 0 | 87.46 |
| teste_estilos_visuais.py | PASS | 0 | 8.55 |
| teste_exportacao.py | PASS | 0 | 19.7 |
| teste_feedback_metricas.py | PASS | 0 | 0.12 |
| teste_ffmpeg_tempo.py | PASS | 0 | 16.31 |
| teste_formatos_ia.py | PASS | 0 | 0.22 |
| teste_gameplay.py | PASS | 0 | 42.79 |
| teste_gancho_capa.py | PASS | 0 | 1.27 |
| teste_gancho_integro.py | PASS | 0 | 0.11 |
| teste_historico_publicacao.py | PASS | 0 | 0.11 |
| teste_idempotencia_fila_capa.py | PASS | 0 | 0.11 |
| teste_indicadores.py | PASS | 0 | 0.17 |
| teste_integridade_render.py | PASS | 0 | 7.74 |
| teste_kwai_diario.py | PASS | 0 | 0.06 |
| teste_liberacao.py | PASS | 0 | 0.87 |
| teste_liberar_corte.py | PASS | 0 | 0.17 |
| teste_link_original.py | PASS | 0 | 0.06 |
| teste_live.py | PASS | 0 | 34.76 |
| teste_memoria_metricas.py | PASS | 0 | 0.11 |
| teste_metricas_publicacoes.py | PASS | 0 | 0.11 |
| teste_motor.py | PASS | 0 | 50.15 |
| teste_pacote.py | PASS | 0 | 4.7 |
| teste_painel.py | PASS | 0 | 0.62 |
| teste_perfis.py | PASS | 0 | 21.69 |
| teste_pipeline_5_agentes.py | PASS | 0 | 11.68 |
| teste_portao_diretor.py | PASS | 0 | 0.17 |
| teste_publicacao_lotes.py | PASS | 0 | 1.12 |
| teste_ranking_metricas.py | PASS | 0 | 0.06 |
| teste_redes_independentes.py | PASS | 0 | 0.41 |
| teste_rejeitar_thumbnail.py | PASS | 0 | 0.17 |
| teste_reposicao.py | PASS | 0 | 1.38 |
| teste_retry_fonte_a1.py | PASS | 0 | 0.16 |
| teste_serie_completa.py | PASS | 0 | 0.17 |
| teste_site_lote1.py | PASS | 0 | 3.38 |
| teste_skills.py | PASS | 0 | 0.17 |
| teste_skills_agentes.py | PASS | 0 | 2.02 |
| teste_skills_novas.py | PASS | 0 | 88.2 |
| teste_temas.py | PASS | 0 | 0.11 |
| teste_thumbnails.py | PASS | 0 | 19.57 |
| teste_tiktok_assistido.py | PASS | 0 | 0.11 |
| teste_trecho_link.py | PASS | 0 | 0.27 |
| teste_versao_refeita.py | PASS | 0 | 0.51 |
| teste_whatsapp.py | PASS | 0 | 16.26 |
