# Central de Automação

A Central fica em **Radar e cortes > Central de Automação** (endereço `#central`). Ela junta os 5 agentes em uma tela só. Vem **desligada**. Desligada, tudo funciona como antes: o Agente 1 segue a meta de cortes por semana.

## O que mudou em relação ao pacote unificado (diagnóstico)

| Pedido do arquivo | Antes | Agora |
|---|---|---|
| Agente 1 só busca e corta quando falta estoque | Cortava até a meta da semana, mesmo com estoque cheio | O estoque manda: abaixo do **mínimo** volta a trabalhar e para no **alvo** (histerese). Também tem intervalo entre rodadas |
| Busca de canais só quando precisa | Buscava todo dia | Com a Central ligada, só busca quando está repondo, a cada N horas |
| Agente 3: ideia livre vira N pautas sem repetir | Não existia | **Linhas de conteúdo**: a IA propõe as pautas (ou você escreve), e o que se parece com algo já feito é barrado |
| Lote de N vídeos independentes | Não existia | Cada pauta vira um projeto e um episódio, com id próprio. Uma pauta nunca é usada duas vezes |
| Modo contínuo | Não existia | A linha repõe o próprio estoque, com mínimo, alvo e limite por dia. Conta o que está em produção e o que espera por você, para não produzir demais |
| Personagens e cenários da biblioteca | Só nas séries | A linha pode usar personagens da biblioteca (com a versão). Fica restrito a estilos animados |
| Estilos do catálogo real | — | Estilo indisponível é recusado. Estilo beta precisa da sua confirmação |
| Aprovado entra no calendário | Só cortes do Agente 1 | Vídeos das linhas também. Um vídeo pode ir a várias redes, uma vez em cada (chave `sha:rede`) |
| Simulação sem efeito | Não existia | "Simular agora" usa os números reais e não grava nada (está coberto por teste) |
| Pausar e retomar | Só por agente | Pausa a Central inteira ou uma linha. O que já está rodando termina; nada novo começa |
| Indicadores | Espalhados | Na visão geral: estoque, rodando, esperando você, falhas em 24 h, próximas postagens |
| Nota 70 e 5 correções | Já existia (esteira) | Sem mudança. A aba Qualidade e revisões mostra a esteira |
| Skills externas | — | Continua a regra: o servidor só detecta ferramentas, e código de fora só entra depois de conferir a licença |

## Regras do estoque

- **Estoque de cortes** é o número de cortes `pronto` que podem ir para a agenda. Com a esteira ligada, cada um precisa do certificado do diretor para o arquivo atual. Com ela desligada, basta não ter sido reprovado.
- **Corte em andamento:** é contado como previsão, multiplicado pela taxa de aprovação do diretor (dos seus últimos 60 dias). Com menos de 5 cortes julgados, a taxa é 60% e a tela avisa que é estimativa.
- **Quanto cortar:** o que falta para o alvo, dividido pela taxa de aprovação. Exemplo: faltam 13 e a taxa é 60%, então ele corta até 22.
- **Demanda por dia** vem da programação diária (a rede que mais pede manda). Sem programação, vem da meta por semana do Agente 1.
- **Modos** Econômico, Equilibrado e Intensivo são só atalhos. Eles preenchem números que continuam visíveis e editáveis:

| Modo | Mínimo | Alvo | Busca de canais | Intervalo entre rodadas | Intervalo entre lotes |
|---|---|---|---|---|---|
| Econômico | 5 | 10 | 48 h | 180 min | 360 min |
| Equilibrado | 9 | 21 | 24 h | 60 min | 120 min |
| Intensivo | 14 | 35 | 12 h | 30 min | 60 min |

- **Sugestões** são regras simples sobre os seus números: o mínimo cobre 3 dias da programação e o alvo cobre 7. **Não é IA.**
- **Histórico:** só guarda quando a decisão muda, com o motivo e os números do estoque naquela hora.

## Linhas de conteúdo

- **Pautas:**
  - "A IA propõe, eu aceito" é o padrão.
  - "A IA escolhe sozinha" aceita a pauta sozinha. Se for um fato sem fonte que abra, a pauta fica "precisa de você".
  - "Eu escrevo" deixa as pautas com você.
- **Fato com fonte:** quando a fonte abre, a pauta mostra "fonte encontrada (o texto não foi conferido)". O servidor **não** confere o conteúdo da página.
- **Publicação automática:** só aprova vídeo que tem o certificado do diretor. Essa aprovação fica registrada como "automação". Sem certificado, nada é aprovado.
- **Agenda:** os vídeos aprovados ocupam os horários das redes marcadas na linha. Se um horário for cancelado ou perdido, o vídeo volta a poder ir para aquela rede.

## Rotas

- `GET /api/v1/automacao/resumo`, `GET|PUT /api/v1/automacao/config` (com `versao`), `POST /api/v1/automacao/simular`, `POST .../pausar` e `POST .../retomar`
- `GET /api/v1/automacao/estoque`, `GET .../eventos`, `GET .../sugestoes` e `POST .../aplicar-sugestoes`
- `GET|POST /api/v1/linhas-conteudo` e `GET|PATCH|DELETE /api/v1/linhas-conteudo/{id}`
- `POST .../{id}/planejar-pautas`, `GET|POST .../{id}/pautas`, `POST .../{id}/iniciar-lote`, `POST .../{id}/pausar|retomar`, `GET .../{id}/episodios` e `GET .../{id}/estoque`
- `PATCH /api/v1/linhas-conteudo/pautas/{id}` com `acao` aceitar, editar, trocar ou bloquear

## Limites honestos

- **Celular:** não foi testado no celular.
- **Fontes:** a conferência só vê se a página abre. Ela não lê o texto.
- **Calendário:** o vídeo de uma linha só entra no calendário com a esteira ligada, porque é a esteira que dá o certificado.
- **Gemini:** o planejamento de pautas usa o Gemini do servidor e conta na cota dele.

## Testes

```
cd servidor
PYTHONPATH=. python3 testes/teste_central_automacao.py
```
