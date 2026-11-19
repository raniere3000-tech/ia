# Reestruturação do site em 5 áreas (Modelo B) — 19/11/2026

Menu com exatamente cinco áreas: **Início, Agentes, Estúdio de Edição, Estúdio IA e Publicações**. Ajustes ficam na engrenagem (fora das cinco).
Tocar em **Agentes** abre o painel dos sete agentes (Modelo B). O Coordenador-Geral fica no cartão do Agente 7, no submenu de Agentes e no atalho global (balão no topo).

Nenhuma tela foi apagada ou reescrita: as áreas novas reagrupam as telas que já existiam. Nenhuma regra de postagem, certificado ou aprovação mudou.

## Onde ficou cada tela (endereço novo ← antigo, o antigo continua abrindo)

| Área | Seção | Endereço novo | Antigo |
|---|---|---|---|
| Início | painel com números reais | `#inicio` | `#inicio` |
| Agentes | Visão geral (7 cartões) — **abre primeiro** | `#agentes/visao-geral` | — (novo) |
| Agentes | Coordenador-Geral | `#agentes/coordenador/<subaba>` (ex.: `ordens:<id>`) | `#coordenador/...` |
| Agentes | Configurar agentes | `#agentes/configurar/<parte>` | `#agente/...` |
| Agentes | Execuções | `#agentes/execucoes` | `#fila` |
| Agentes | Aprovações (lista; com id abre a revisão) | `#agentes/aprovacoes[/<projeto>]` | `#revisar/<projeto>` |
| Agentes | Automação (Central) | `#agentes/automacao/<aba>` | `#central/...` |
| Agentes | Memória e aprendizado | `#agentes/memoria` | `#coordenador/memoria` |
| Agentes | Skills e ferramentas | `#agentes/skills` | `#central/historico` |
| Agentes | Capas (Agente 6) | `#agentes/agente/6/<aba>` | `#thumbnails/...` |
| Estúdio de Edição | Começar (novo, entrada) | `#edicao/inicio` | — |
| Estúdio de Edição | Montagem manual / Radar / Cortes / Templates / Legendas e efeitos / Áudio e vozes / Live / Meus projetos | `#edicao/manual`, `radar`, `cortes`, `templates`, `legendas-efeitos`, `vozes`, `live`, `projetos` | `#manual`, `#radar`, `#cortes`, `#templates`, `#estilos`, `#vozes`, `#live`, `#projetos` |
| Estúdio IA | Começar (novo, entrada) | `#estudio-ia/inicio` | — |
| Estúdio IA | Criar com IA / Séries / Produção em lote / Biblioteca criativa / Vozes / Animado / Projetos IA | `#estudio-ia/criar`, `series`, `lote`, `biblioteca`, `vozes`, `animado`, `projetos` | `#ia`, `#series`, `#automatico`, `#galeria`, `#vozes`, `#video`, `#projetos` |
| Publicações | Posts e contas (abre primeiro) | `#publicacoes/calendario` | `#agendar` |
| Publicações | Programação diária / Calendário das linhas / Resultados | `#publicacoes/programacao`, `linhas`, `resultados` | `#agente/programacao`, `#central/calendario`, `#agente/desempenho` |
| Publicações | Ajustes do Agente 2 (atalho) | abre `#agentes/configurar/postagem` | `#agente/postagem` |
| — | Ajustes (engrenagem) | `#config` | `#config` |

Vozes e Projetos aparecem nos dois estúdios: o endereço guarda de qual estúdio você veio. Projetos abre filtrado por esse estúdio (a lista é a mesma).

## Arquivos

- `frontend/src/navigation/rotas.ts` — registro único das áreas/seções e o roteador (endereços novos e antigos).
- `frontend/src/App.tsx` — menu lateral e barra de baixo lidos do registro; atalho do Coordenador; troca o endereço antigo pelo novo sem criar passo no Voltar.
- `frontend/src/pages/AgentesHome.tsx` — Central de Agentes (7 cartões).
- `frontend/src/components/PainelInicio.tsx`, `PainelPartes.tsx`, `lib/dashboard.ts` — Início com números do servidor.
- `frontend/src/pages/EdicaoHome.tsx`, `EstudioIAHome.tsx`, `components/Continuar.tsx` — entradas dos estúdios.
- `frontend/src/components/CoordenadorRapido.tsx` — atalho global (o mesmo chat da tela do Coordenador, mesmo rascunho).
- `frontend/src/pages/Revisar.tsx` — sem vídeo escolhido, mostra a lista do que espera a sua decisão.
- `frontend/src/pages/Projetos.tsx` — filtro Todos / Estúdio de Edição / Estúdio IA.
- `servidor/painel.py` + rota `GET /api/v1/dashboard/resumo?periodo=hoje|7d|30d` em `api_v1.py` — **só leitura**.

## Números do painel (servidor)

Tudo vem do banco e dos arquivos do servidor. O que o servidor não sabe vai como `null` e aparece como "Não disponível" (nunca 0).
Vídeos (por arquivo distinto), tarefas (fila) e envios (post × rede) são contados separados. "Aprovados" exige certificado final válido do diretor e só existe com a esteira ligada.
Tempo trabalhado = soma da coluna `decorrido` da fila (tempo rodando, sem a espera). Previsão só quando medida neste servidor.
Servidor antigo (sem a rota nova): os cartões usam `/api/v1/coordenador/agentes` e as contagens por período ficam "Não disponível".

## Testes

- `cd frontend && npm test` — 11 testes do roteador (mapa antigo → novo, ida e volta, endereços estranhos, nada de senha no endereço).
- `cd servidor && python3 testes/teste_painel.py` — 27 testes do painel (login, contagens, períodos, só leitura).
- `frontend/testes/e2e-areas.cjs` + `e2e-servidor.py` — passeio no site com servidor real (95 conferências em 360×800, 390×844, 768×1024, 1024×768 e 1440×900).
- `npm run build` sem erros.

## Para voltar atrás

Tudo é só site + uma rota de leitura. Para desfazer: `git revert` do commit desta mudança (o servidor continua funcionando com ou sem a rota `/api/v1/dashboard/resumo`). Nenhum dado ou banco foi migrado.

## Ainda não testado

No celular de verdade (Termux + navegador do Android) e com contas reais.
