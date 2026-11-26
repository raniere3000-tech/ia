# Fase 5 — Inteligência e feedback: quatro cartões pequenos

**Pré-condição:** F4 aceita. Reutilizar `aprendizado.py`, `inteligencia_viral.py`, `coordenador.py`, `painel.py` e telas existentes; só adicionar área dedicada se a navegação atual não atender.

### F5.01 — Painel por vertente (15–35 min)
Mostrar indicadores reais filtrados por **Cortes / Criação IA**, plataforma, canal e período. Sem duplicar snapshots. 'Indisponível' se API não fornecer métrica.

### F5.02 — Vídeos vencedores e rastreabilidade (20–35 min)
Listar top vídeos com fonte, versão, gancho, template, efeitos aplicados, capa e horário, ligados aos dados capturados. Diferenciar dados ausentes de zero.

### F5.03 — Feedback específico por agente (20–40 min)
Coordenador gera recomendações para A1 (ganchos), A3 (roteiros), A5 (efeitos), A6 (capas), A2 (horários), A4 (critérios) baseadas em evidência. Dados insuficientes = não concluir causalidade. Não mutar prompt/config automaticamente.

### F5.04 — Memória versionada e aprovação (20–40 min)
Guardar hipótese, amostra, responsável, aprovação, teste controlado e rollback usando mecanismo existente de `aprendizado.py`; preservar DNA por canal e distinguir as duas vertentes. Não criar agente 8.

**Fecho:** `teste_aprendizado.py`, `teste_coordenador.py`, `teste_painel.py` e testes frontend; PR sem merge.
