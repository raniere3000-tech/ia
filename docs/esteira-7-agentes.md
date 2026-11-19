# Esteira obrigatória dos 7 agentes (19/11/2026)

Fluxo de todo vídeo:

| # | Etapa | Corte | Vídeo próprio |
|---|-------|-------|---------------|
| 1 | Produção | Agente 1 escolhe o trecho (`agente.processar_video`) | Agente 3 cria roteiro, narração, imagens e clipes (`produtor`) |
| 2 | Diretor: avaliação inicial | `diretor_qualidade.avaliar_previo_corte`, antes de editar (duração, gancho, fim de frase, fala) | `avaliar_criativo` (cenas e roteiro), antes da montagem |
| 3 | Editor: edição e exportação | Agente 5 (`editor_ia.rodar`) | montagem do Agente 3 (`produtor.etapa_final`); o registro diz quem fez |
| 4 | Diretor: arquivo final | `avaliar_final` + certificado preso ao SHA-256 | igual |
| 5 | Capa | Agente 6 (`thumbnails`), capa presa ao SHA do vídeo | igual |
| 6 | Coordenador: liberação final | `esteira.revisar_pacote` confere diretor, avaliação inicial, capa, direitos, link original (cortes) e título; pacote preso ao hash do vídeo + capa + metadados | igual; a sua aprovação em Revisar vale como liberação se o pacote estiver completo |
| 7 | Publicador: agendamento | post criado (só com liberação) | igual |
| 8 | Publicador: envio às redes | link de cada rede | igual |

## Onde fica

- `servidor/esteira.py` faz o registro (tabelas `esteira_videos`, `esteira_etapas` e `esteira_historico`, migração 12) e o condutor (`avancar` e `varrer`).
- O condutor só segue A6 → A7 → A2 a partir do que já foi provado. O vigia do Coordenador chama `varrer()` a cada ~20 s.
- Uma etapa só fica "concluída" com recibo, que é a prova:
  - id do corte;
  - laudo do diretor;
  - SHA do arquivo;
  - certificado;
  - capa;
  - pacote;
  - post;
  - link da rede.
- O tempo ativo de cada etapa é medido e somado. A espera na fila fica separada.
- Cada etapa tem um destes estados:
  - pendente;
  - esperando a etapa anterior;
  - na fila;
  - trabalhando;
  - esperando você;
  - falta um recurso;
  - corrigindo;
  - concluída;
  - reprovada;
  - revisão manual;
  - falhou;
  - cancelada;
  - não se aplica (com motivo).

## Correções (no máximo 5 por etapa; falha técnica não conta)

- **Avaliação inicial do corte reprovada.** O Agente 1 ajusta o começo e o fim (`ajustar_inicio` e `ajustar_fim`, alvo `agent1`) e o diretor confere de novo. Se não houver conserto, o trecho é descartado sem renderizar.
- **Arquivo final reprovado.** O Agente 5 corrige o plano. Cenas apontadas voltam para o Agente 3. Direitos ficam com você.
- **Pacote reprovado por você.**
  - Vídeo: o corte volta para o editor e o diretor; o vídeo próprio vai para o Agente 3 como pedido de alteração.
  - Capa: o Agente 6 faz um pedido novo de capa.
- **Arquivo mudou depois da aprovação.** Capa e liberação voltam a esperar, e só o necessário é refeito.

## Legenda em cima de texto do vídeo (pedido de 19/11)

- Na liberação final, o Coordenador confere se o vídeo já tinha texto na tela: legenda embutida, letreiro, nome, placar ou marca d'água (`texto_tela.py`).
- Ele tira 5 quadros do arquivo final e manda para a IA de imagem (Gemini), que diz onde fica cada texto. Uma conferência por versão do arquivo (tabela `texto_tela`, migração 13).
- Se o texto fica por baixo ou encostado na nossa legenda, o corte volta sozinho para o editor (`editor.legenda`), com a posição livre: embaixo, no meio ou em cima.
- O editor monta de novo a partir do trecho original guardado (sem a nossa legenda, em `agente_trabalho/esteira/legenda/`), o diretor confere, e só então o arquivo é trocado. Capa e liberação são refeitas.
- No máximo 5 voltas. Sem lugar livre, sem trecho guardado (cortes antigos) ou no limite, o pacote espera você: em Coordenador > Aprovações dá para mudar a legenda de lugar ou liberar mesmo assim.
- Se a IA falhar 3 vezes, o pacote segue com o aviso "não deu para conferir texto na tela".
- Vídeos próprios (Agente 3) não levam legenda por cima: o item não se aplica.

## Travas de publicação (política "completa", ligada por padrão)

- `postagem.criar_post` recusa o vídeo sem liberação do Coordenador e diz o que falta.
- `conferencia` exige a liberação (`coordenador.exigir_liberacao_efetiva`).
- A programação diária (`agenda_postagem.elegiveis`, `linhas_conteudo.ativos_para`) e o agendador antigo (`agente.a7_liberou`) só pegam vídeos liberados.
- Um post antigo que esbarra só em etapa da esteira não vira erro: espera e tenta a cada 10 minutos, e só vira erro depois de 24 h.
- Com a política completa, editor e diretor ficam sempre ligados (`pipeline.ligado()`).
- Política: `GET` e `PUT /api/v1/esteira/politica`, com versão, nas chaves:
  - `completa`;
  - `capa_obrigatoria`;
  - `liberacao_automatica` (o Coordenador libera sozinho quando todos os itens passam).

## APIs

- `GET /api/v1/esteira`: resumo, política e vídeos.
- `GET /api/v1/esteira/execucoes`.
- `GET /api/v1/esteira/execucoes/{corte-ID|render-ID}/timeline`.
- `POST .../avancar`.
- `GET /api/v1/esteira/diagnostico`.
- `POST /api/v1/esteira/conciliar/simular`: não muda nada.
- `POST /api/v1/esteira/conciliar`: exige `{"confirmar": true, "videos": [...]}`.

Vídeos postados e cancelados ficam de fora da recuperação. Ela pede só a etapa que falta.

## Site

- **Agentes > Esteira dos 7 agentes** (Coordenador > aba Esteira) mostra:
  - a política;
  - os filtros;
  - cada vídeo com as 8 etapas, a prova, o tempo e o histórico;
  - a recuperação com simulação e confirmação.
- **Início, "Os 7 agentes agora"** mostra o estado real de cada agente, juntando a fila com a esteira:
  - trabalhando;
  - na fila;
  - esperando você;
  - bloqueado;
  - esperando a etapa anterior;
  - sem trabalho.

  A "Produção por agente" mostra as etapas concluídas com prova.

## Limitações conhecidas

- Vídeos próprios: o Agente 5 não edita. A etapa 3 é a montagem do Agente 3, e o registro diz isso.
- Tempos muito curtos (liberação, agendamento) aparecem como 0 s porque foram medidos assim.
- Com a liberação automática desligada, cada vídeo espera você em Liberar.
- Com o Agente 6 no modo supervisionado, cada capa espera a sua escolha.
- Sem Pillow no Termux, a capa fica em "falta um recurso" e nada é postado (`pkg install python-pillow`).
- Teste: `python3 testes/teste_esteira_7.py`, com FFmpeg de verdade. São simulados só a IA e o envio às redes. Os testes antigos rodam com `ESTEIRA_COMPLETA=0`.
- Não testado no celular.
