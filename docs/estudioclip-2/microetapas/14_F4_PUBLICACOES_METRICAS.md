# Fase 4 — Publicações e métricas: quatro cartões pequenos

**Pré-condição:** F3 aceita. Reutilizar `postagem.py`, `agenda_postagem.py`, `aprendizado.py`, `painel.py`, integrações atuais.

### F4.01 — Status individual por rede (15–30 min)
Na lista de posts, manter registro individual YouTube/TikTok/Instagram/etc, inclusive vídeo publicado em uma e pendente em outra. Filtro por rede + situação; sem alterar postagem já concluída.

### F4.02 — Reenvio e agendamento em lote (20–40 min)
Reutilizar slots e idempotência existentes; seleção de múltiplos posts, intervalo entre envio e retry **apenas** da rede falha. Contas reais não podem ser usadas em testes automatizados.

### F4.03 — Métricas acessíveis (20–40 min)
Inventariar endpoints/permissões realmente disponíveis; utilizar snapshots em `aprendizado.py` e armazenar somente métricas retornadas (ex.: views e engajamento). Não inventar retenção onde API não fornece. Preservar origem, data e tipo de rede.

### F4.04 — Histórico de publicação por versão (15–30 min)
Conectar ID da rede e métricas com o vídeo/render/capa/gancho usados; só adicionar campos aditivos se ausentes. Validar que edição posterior não altera histórico de publicação anterior.

**Fecho:** `teste_agenda_agente2.py`, `teste_redes_independentes.py`, `teste_aprendizado.py`, `teste_painel.py`; PR sem merge.
