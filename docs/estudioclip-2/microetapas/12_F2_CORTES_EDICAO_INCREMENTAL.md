# Fase 2 — Cortes e edição: quatro cartões pequenos

**Pré-condição:** Fase 1 aceita. Não criar novo motor. Priorizar os módulos existentes `agente.py`, `editor_ia.py`, `contratos.py`, `renderizador.py`, `visual_presets.py`, `pipeline.py`.

### F2.01 — Gancho íntegro (15–30 min)
A1 conserva frases inteiras (início/fim e pausas), transcrição preferencial mas não obrigatória, evita cortar palavra ou abandonar fonte sem legenda. Testes focais com frases incompletas e com vídeo sem legenda. Resultado: gancho + timestamps + justificativa persistidos.

### F2.02 — Efeitos reais básicos (20–40 min)
A5 reaproveita EditPlan e render FFmpeg. Testar zoom pontual, B-roll licenciado disponível, transição simples e legendas dinâmicas. **Obrigatório comparar resultado renderizado com plano**, contar efeitos planejados/aplicados e falhas; sem efeito real não declarar 'editado'. Evitar implementar biblioteca inteira de efeitos agora.

### F2.03 — Integridade de render (15–30 min)
Testar áudio sincronizado, frames pretos inesperados, duração, codec, volume e travamento em meio ao vídeo. Quando falhar, manter o original/versão anterior; retry limitado.

### F2.04 — DNA mínimo de corte (15–30 min)
Salvar por canal apenas template, fonte, cor, legenda, intensidade de zoom e ritmo; preferir configuração existente de templates. Sem novo banco se campos atuais cobrirem. Testar escolha manual e uso pelo agente.

**Fecho:** rodar `teste_estilos_agente1.py`, `teste_estilos_editar.py`, `teste_motor.py`, `teste_exportacao.py`, `teste_pipeline_5_agentes.py` e frontend afetado; PR separado, flags desligadas e sem merge.
