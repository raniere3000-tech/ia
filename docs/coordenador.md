# Agente 7: Coordenador-Geral

O Coordenador é o agente com quem você conversa. Você pede em português, ele monta um plano com os agentes que já existem, você confirma e ele acompanha tudo até o fim.

Ele **não faz** vídeo, corte nem capa. Ele chama quem faz:

| Agente | O que o Coordenador pede |
|---|---|
| Agente 1 (cortes) | Cortar um link, cortar por tema, rodar o agente de cortes ou procurar canais (radar) |
| Agente 3 (vídeos) | Produzir vídeos sobre um tema, com estilo, voz, formato e duração |
| Agente 4 (diretor) | Nada direto: o Coordenador só lê a aprovação do diretor para o arquivo |
| Agente 5 (editor) | Nada direto: o vídeo final já vem do editor |
| Agente 6 (capas) | Fazer capas para cada vídeo |
| Agente 2 (postagem) | Agendar o pacote liberado nas redes, no dia e hora pedidos |
| Central | Pausar e retomar a automação |

Tela: **Automação e agentes > Coordenador** (`#coordenador`). Também há um botão na página inicial ("Falar com o Coordenador") e outro no topo da Central.

## Como funciona

1. **Você pede.** Exemplo: "Faça 3 vídeos sobre a história do café, voz masculina, estilo documentário, 2 capas por vídeo, postar no YouTube amanhã às 18h".
2. **Ele entende.** Primeiro pelas regras em português, que são rápidas e não gastam IA. Só se as regras não entenderem é que ele pergunta ao Gemini, e só se houver chave e a opção estiver ligada. A IA só pode devolver uma ação do catálogo. Qualquer outra coisa é recusada.
3. **Ele propõe um plano.** O plano diz qual agente faz o quê e em que horários. Se faltar algo (tema, rede, dia, hora), ele pergunta. Se algo impede (conta da rede não conectada, horário que já passou, estilo que não roda no celular, capas sem o Pillow), ele avisa.
4. **Você confirma.** Nada começa antes disso. Confirmar duas vezes não cria nada a mais.
5. **Ele distribui e acompanha.** Cada pedido vira uma ordem com tarefas em sequência:
   - planejar os temas: com IA, assuntos diferentes; sem IA, o mesmo tema com a instrução de mostrar um aspecto diferente em cada vídeo;
   - produzir cada vídeo (Agente 3);
   - fazer as capas (Agente 6);
   - liberar o pacote final (você);
   - agendar (Agente 2).

   Uma tarefa só fica "pronta" quando o banco confirma, ou seja, pela situação do projeto, do trabalho na fila ou do pedido de capa. Se uma etapa falha, as que dependem dela ficam **bloqueadas**, com o motivo.
6. **Você libera o pacote.** O pacote é o vídeo final mais a capa escolhida, presos pelo SHA-256 dos dois. Você pode escolher a capa ali mesmo. Se o vídeo ou a capa mudarem depois, a liberação cai e o pacote volta para você.
7. **O Agente 2 agenda.** Ele usa o mesmo caminho de sempre (`aprovacoes.aprovar`), então todos os portões continuam valendo. Se a produção passou do horário pedido, o vídeo vai para o dia seguinte no mesmo horário, e a ordem mostra isso.

## Horário sem vídeo: reposição automática

O Agente 2 confere isso sempre, a cada volta da programação (e também no caminho antigo, sem programação diária).

1. **Você posta antes da hora.** Se você toca em "Postar agora" num post que estava preso a um horário da programação, o vídeo sai na hora e aquele horário **volta a ficar livre**. O corte que já saiu não volta para a fila, então ele não é postado duas vezes.
2. **O horário livre recebe o próximo vídeo aprovado** pelo diretor, no mesmo horário de antes.
3. **Não há vídeo aprovado?** Se algum horário das próximas 24 horas está vazio e não há vídeo para ele, o Agente 2 pede mais vídeos ao Coordenador. O Coordenador abre sozinho uma ordem de reposição e manda o Agente 1 cortar. Os cortes novos passam pelo editor e pelo diretor como sempre, e o primeiro aprovado vai para o horário vazio.

Sem pedidos repetidos: só uma reposição por vez e, depois, no mínimo 60 minutos até a próxima (dá para mudar). Com a Central pausada, ou com a opção desligada em **Coordenador > Configurações**, ele não pede nada. A reposição só manda **cortar**. Nada é postado sem o diretor e os portões de sempre.

### Vídeos próprios de uma ordem (ex.: 10 vídeos, um por dia)

Se você posta antes da hora um vídeo de uma ordem do Coordenador, o Agente 2 avisa que aquele horário ficou vazio e o Coordenador **adianta a série**: o próximo vídeo vai para o horário que ficou livre, e os seguintes sobem um horário cada. Continua um por dia; a série só termina um dia antes. Se o próximo vídeo ainda está sendo feito pelo Agente 3, ele já leva o horário novo e sai nele assim que você liberar. Vídeo que já está saindo, que já saiu ou que veio da programação diária não é mexido.

## Corrigir

No pacote, "Pedir correção" tem duas opções:

- **Refazer o vídeo:** o pedido vai ao Agente 3 pelo caminho normal de correção. Depois disso, as capas e a liberação são refeitas para a versão nova.
- **Refazer só a capa:** o Agente 6 faz capas novas, com o seu texto como orientação. O vídeo não é refeito.

O limite é de **5 correções por etapa**, e dá para mudar nas configurações do Coordenador. Passou do limite, o pedido volta com o erro 429.

## Modos

| Modo | O que muda |
|---|---|
| **Supervisionado** (padrão) | Você libera cada pacote. |
| **Automático** | O Coordenador libera sozinho o pacote que o diretor aprovou e que já tem capa escolhida. |

A opção **"O Agente 2 só posta vídeo liberado aqui"** (desligada por padrão) faz o Agente 2 barrar qualquer post sem liberação válida do Coordenador para aquele arquivo.

## Memória

- Uma preferência começa como **proposta** e só vale depois que você confirma. Você pode criar uma pelo chat ("lembre que eu prefiro voz masculina") ou pela aba Memória.
- O escopo diz onde ela vale: tudo, uma plataforma, um canal, uma linha ou série, um tema, um projeto ou um vídeo. Quando duas memórias falam da mesma coisa, vence a mais específica e, depois, a mais recente.
- **O que você diz no pedido sempre vence a memória.** "Neste vídeo use voz feminina" vale só para aquela ordem e não muda a preferência guardada.
- Toda mudança cria uma versão nova: criar, confirmar, editar, desativar e voltar para uma versão antiga. Nada é apagado.
- A memória só guarda voz, estilo, formato, duração, ritmo, capas por vídeo e composição da capa, além do texto. **Ela nunca guarda permissão:** pedidos como postar, aprovar, mudar orçamento ou mudar conta são descartados.

## Aprendizado

A aba Aprendizado mostra padrões tirados do que aconteceu de verdade neste servidor, sempre com a evidência:

- a composição de capa que você escolhe (a partir de 5 escolhas, quando uma passa de 70%);
- falhas repetidas na fila (3 ou mais em 7 dias);
- correções que você pede muito (3 ou mais em 30 dias);
- trabalhos que ficaram mais lentos (só quando há amostras).

**Nada muda sozinho.** A única ação é "Propor como memória", e a memória ainda precisa da sua confirmação.

## Agentes e tempos

A aba Agentes mostra, para cada agente:

- o que ele está fazendo agora;
- quantos trabalhos estão na fila;
- quantos foram feitos e quantos falharam em 24 horas;
- o tempo médio, medido nos trabalhos deste servidor, com o número de amostras;
- o custo registrado em 30 dias.

Sem medida, aparece "sem medida ainda" e "estimativa indisponível". O "quanto falta" de uma ordem soma as médias medidas, um vídeo por vez, e mostra à parte quantas decisões dependem de você.

## Histórico

Tudo fica no histórico: o que você pediu, o plano, o que foi mandado a cada agente, as liberações, as correções e as memórias. Cada registro carrega o hash do anterior. O botão "Conferir o histórico" mostra se algum registro foi mexido por fora.

## API (`/api/v1/coordenador`, com sessão)

| Rota | Para quê |
|---|---|
| `POST /interpretar` `{texto, chave?}` | Conversa: responde na hora, cria uma proposta de ordem ou uma proposta de memória |
| `GET /conversa` | As mensagens guardadas |
| `GET /catalogo` | As ações permitidas e se a IA está disponível |
| `GET /ordens?status=` / `POST /ordens` | Lista de ordens / ordem estruturada (`intencao`, `parametros`) |
| `GET /ordens/{id}` | Ordem com tarefas, liberações, tempo que falta e histórico |
| `POST /ordens/{id}/parametros` | Completa a proposta (`parametros`, `versao_plano`) |
| `POST /ordens/{id}/confirmar` | Confirma (`versao_plano`); confere tudo de novo na hora |
| `POST /ordens/{id}/pausar`, `/retomar`, `/cancelar` | Controle da ordem |
| `GET /agentes` | Painel dos agentes |
| `GET /aprovacoes?estado=pendente` | Pacotes para liberar |
| `POST /aprovacoes/{id}/capa` | Escolhe a capa do pacote |
| `POST /aprovacoes/{id}/decidir` | `{decisao: aprovar ou reprovar, pacote_hash, alvo, comentario, sem_capa}` |
| `GET/POST /memorias`, `GET/PATCH /memorias/{id}` | Memória |
| `POST /memorias/{id}/confirmar`, `/desativar`, `/reverter` | Confirmar, desativar e voltar de versão |
| `POST /feedback` | Avaliação (-1, 0 ou 1) de vídeo, capa, pacote, ordem ou agente |
| `GET /aprendizado/sugestoes` | Sugestões com evidência |
| `POST /aprendizado/sugestoes/{id}/propor` ou `/dispensar` | Vira proposta de memória, ou some da lista |
| `GET /eventos`, `GET /historico/conferir` | Histórico e conferência da corrente de hashes |
| `GET/POST /config` | Modo, exigir liberação, limites, uso da IA e reposição automática (`reposicao_automatica`, `reposicao_intervalo_min`) |

Erros: 400 (pedido inválido ou fora do catálogo), 404, 409 (falta dado, proposta ou pacote mudou), 429 (limite de correções ou de pedidos por hora).

## Banco

A migração 11 é só aditiva e cria estas tabelas:

- `coordenador_ordens`
- `coordenador_tarefas`
- `coordenador_eventos`
- `coordenador_feedback`
- `coordenador_memorias`
- `coordenador_memoria_versoes`
- `coordenador_memoria_evidencias`
- `coordenador_aprovacoes`

## O que não foi instalado

Mem0, LangGraph, CrewAI e afins **não foram instalados**. O Coordenador usa só o que já existe no servidor: SQLite, a fila, o Gemini (opcional) e os módulos dos agentes.

## Testes

`servidor/testes/teste_coordenador.py` usa o servidor HTTP de verdade, o SQLite, o FFmpeg, o Pillow e o Agente 6 de verdade. O Agente 3 é trocado por um produtor falso, porque o de verdade precisa do Gemini. São 80 conferências, que cobrem os cenários da especificação que dá para testar sem celular e sem contas reais.

**Não testado no celular, nem com o Gemini, o YouTube ou o TikTok de verdade.**
