# Matriz de competências do Editor Pro

Auditoria estática do HEAD base. Executor indica código localizado. A prova local é acrescentada no checkpoint correspondente. Todas as linhas têm validação Termux pendente. Para lacunas, conservar a edição existente sem anunciar a técnica como aplicada. O custo por competência será medido com a fixture correspondente.

| ID | Especialidade | Competência | Status na base | Evidência, fixture ou lacuna |
|---|---|---|---|---|
| C01.01 | Montagem | Jump cuts | Validada no Linux | teste_efeitos_reais confirma mudança visual com cortes entre trechos; montagem com FFmpeg e recibo por SHA. |
| C01.02 | Montagem | J/L cuts | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C01.03 | Montagem | match cuts | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C01.04 | Montagem | montagem paralela | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C01.05 | Montagem | cortes por emoção | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C01.06 | Montagem | continuidade narrativa | Em outro agente | produtor.roteiro e diretor_qualidade.avaliar_criativo: coerência do roteiro; decisão de montagem A5 pendente. |
| C02.01 | Ritmo | Speed ramp | Parcial | Mudança de velocidade por trecho comprovada com A/V; curva contínua pendente. |
| C02.02 | Ritmo | câmera lenta | Validada no Linux | teste_efeitos_reais renderiza trecho a 0,5× e verifica tempo A/V, timestamps e SHA. Fallback: trecho em 1×. |
| C02.03 | Ritmo | freeze frame | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C02.04 | Ritmo | pattern interrupt | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C02.05 | Ritmo | cortes no beat | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C02.06 | Ritmo | preservar gancho | Validada no Linux | teste_editor_timeline protege correções, teste_efeitos_reais renderiza abertura inteira e registra o intervalo. Flag A5_EDITOR_PRO. |
| C03.01 | Enquadramento | Rastreamento facial | Parcial | agente.ajustar_camera localiza webcam estática; não há rastreamento temporal A5 identificado. |
| C03.02 | Enquadramento | rastreamento de objeto | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C03.03 | Enquadramento | zoom inteligente | Executor | editor_ia._finalizar_efeitos; teste_efeitos_reais compara RGB para zoom por intervalo; seleção adaptativa pendente. |
| C03.04 | Enquadramento | reenquadramento | Executor | editor_ia._quadro_roi / teste_efeitos_reais: região estática na borda, confirmação por pixels e fallback de encaixe. |
| C03.05 | Enquadramento | estabilização | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C03.06 | Enquadramento | multicâmera | Parcial | agente.filtro_video compõe HUD/webcam do mesmo sinal; edição multicâmera real pendente. |
| C04.01 | Cor | Correção de cor | Validada no Linux | editor_ia._filtros_cor / teste_efeitos_reais: cor SDR alterada em frames, com fallback quando falta filtro. |
| C04.02 | Cor | grading | Parcial | Saturação, contraste, exposição e temperatura tipados no editor_ia. Perfis de grading por conteúdo pendentes. |
| C04.03 | Cor | LUT | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C04.04 | Cor | balanço de branco | Parcial | Ajuste de temperatura implementado e renderizado em combinação. Medição de branco neutro e fixture isolada pendentes. |
| C04.05 | Cor | exposição | Validada no Linux | Teste de cor mede aumento de luminância após ajuste de exposição. |
| C04.06 | Cor | correspondência de cenas | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C05.01 | Áudio | Redução de ruído | Parcial | editor_ia._filtros_audio usa afftdn; teste de cadeia aprovado, falta fixture isolada de redução de ruído. |
| C05.02 | Áudio | EQ | Parcial | Equalizador tipado executado na cadeia e resposta aos 440 Hz medida; falta fixture isolada. |
| C05.03 | Áudio | compressão | Parcial | Compressor tipado executado na cadeia; falta curva isolada com medição de envelope. |
| C05.04 | Áudio | ducking | Validada no Linux | teste_efeitos_reais mede atenuação de trilha durante voz e recuperação na pausa. |
| C05.05 | Áudio | normalização | Executor | editor_ia._executar_importado_base / _finalizar_efeitos; fixture de LUFS pendente. |
| C05.06 | Áudio | separação voz/música | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C06.01 | Design sonoro | Foley | Em outro agente | produtor e perfil agente3.dialogo; render A5 pendente. |
| C06.02 | Design sonoro | whoosh | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C06.03 | Design sonoro | impactos | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C06.04 | Design sonoro | risers | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C06.05 | Design sonoro | ambiência | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C06.06 | Design sonoro | sincronização de efeitos | Validada no Linux | teste_efeitos_reais demonstra áudio presente após o início programado; recibo com SHA do asset. |
| C07.01 | VFX | Chroma key | Validada no Linux | editor_composicao e teste_efeitos_reais: chroma verde removido da camada somente no intervalo selecionado. |
| C07.02 | VFX | máscaras | Validada no Linux | Máscara retangular e máscara externa comprovadas por pixels, com SHA da máscara. |
| C07.03 | VFX | rotoscopia | Parcial | Executor aplica máscara fornecida pelo plano. Rastreamento e criação de máscara por objeto ainda faltam. |
| C07.04 | VFX | motion blur | Validada no Linux | Suavização por mistura temporal tmix; teste mostra diferença de pixels. |
| C07.05 | VFX | camadas | Validada no Linux | Overlay temporal por asset e posições tipadas. Teste por pixels confirma frente e fundo. |
| C07.06 | VFX | remoção de fundo | Parcial | Remoção por chroma ou máscara fornecida. Segmentação automática permanece aberta. |
| C08.01 | Motion | Keyframes | Validada no Linux | teste_efeitos_reais mede a posição de camada animada em instantes diferentes. |
| C08.02 | Motion | easing | Validada no Linux | Fixture compara posição em interpolação linear e suave em MP4s reais. |
| C08.03 | Motion | parallax | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C08.04 | Motion | animação 2D | Parcial | Executor move elementos 2D com keyframes. Rig de personagens existe no A3; conexão específica pendente. |
| C08.05 | Motion | elementos 3D | Em outro agente | motor3d / produtor; entrada A5 independente pendente. |
| C08.06 | Motion | infográficos | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C09.01 | Legendas | Palavra a palavra | Validada no Linux | Teste em vídeo com duas palavras confirma existência de legenda indexada por tempo e render da ênfase. |
| C09.02 | Legendas | tipografia cinética | Parcial | ASS com transformação de escala temporal e vídeo com ênfase; falta fixture de variação de escala isolada. |
| C09.03 | Legendas | destaque semântico | Parcial | Termos explícitos passam por validação e são destacados em pixels. Seleção semântica autônoma pendente. |
| C09.04 | Legendas | evitar sobreposição | Parcial | editor_ia.corrigir move legenda por ação do Coordenador; detecção autônoma pendente. |
| C09.05 | Legendas | texto rastreado | Pendente | Executor específico A5 não localizado. Fixture, custo e evidência de saída pendentes. |
| C09.06 | Legendas | zonas seguras | Parcial | agente.montar_ass reserva margens e alturas; fixture com zonas por rede pendente. |
| C10.01 | Arte | Identidade visual | Parcial | agente.tpl / render por template e perfil; paridade de identidade nas duas origens pendente. |
| C10.02 | Arte | composição cinematográfica | Parcial | agente.filtro_video aplica composição por modelo; planejamento A5 pendente. |
| C10.03 | Arte | B-roll | Executor | editor_ia._finalizar_efeitos e teste_efeitos_reais: asset registrado, autoria declarada e pixels azuis na saída. |
| C10.04 | Arte | estética por nicho | Parcial | agente e visual_presets aplicam estilos; seleção A5 por nicho pendente. |
| C10.05 | Arte | transições | Executor | editor_ia._passo_final e teste_efeitos_reais: fade medido; transições entre tomadas pendentes. |
| C10.06 | Arte | coerência visual | Parcial | templates e snapshots A3 em produtor; teste comparativo A5 pendente. |
| C11.01 | Finalização | FPS | Validada no Linux | Finalização a 25 fps confirmada por ffprobe; matriz com VFR pendente. |
| C11.02 | Finalização | compressão | Validada no Linux | Recibo confirma H.264 e perfil CRF; teste decodifica o MP4 inteiro. |
| C11.03 | Finalização | bitrate | Validada no Linux | Parâmetro VBV com limite tipado; ffprobe confirma bitrate médio abaixo de 650 kbps na fixture. |
| C11.04 | Finalização | sincronia A/V | Parcial | editor_ia corta A/V e renderizador.conferir mede streams; fixture de sincronismo após montagem pendente. |
| C11.05 | Finalização | multiformato | Executor | contratos.ASPECTOS / editor_ia._executar_importado_base; fixtures nas quatro proporções pendentes. |
| C11.06 | Finalização | validação do render | Executor | renderizador.conferir / teste_integridade_render sob RENDER_INTEGRIDADE, com SHA no recibo. |
| C12.01 | Inteligência | Referências | Em outro agente | capacidades.youtube-api e perfil radar.temas; entrada no planejador A5 pendente. |
| C12.02 | Inteligência | aprendizagem por retenção | Parcial | aprendizado.analisar / indicadores por contexto; recomendar efeitos do A5 com dados comparáveis pendente. |
| C12.03 | Inteligência | efeitos adaptativos | Parcial | editor_ia.corrigir adapta após QA; seleção inicial por nicho/confiança/custo pendente. |
| C12.04 | Inteligência | A/B | Parcial | aprendizado.criar_experimento; integração de variantes Editor Pro pendente. |
| C12.05 | Inteligência | memória | Parcial | pipeline.guardar_plano e aprendizado.pesos_ativos; avaliação por versão existe, feedback específico A5 pendente. |
| C12.06 | Inteligência | correção autônoma | Executor | editor_ia.rodar / pipeline: ações tipadas, revisão por limite e interrupção sem mudança; revalidar focal. |
