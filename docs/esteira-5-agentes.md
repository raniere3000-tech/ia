# Esteira dos 5 agentes

Esta é a esteira da especificação técnica dos 5 agentes. Ela fica **desligada** até você ligar em **Agentes > 4 e 5 · Diretor e editor**. A variável `PIPELINE_V2=1` também liga. Com a esteira desligada, tudo funciona como antes.

## Caminho de cada vídeo

- **Agente 1 (cortes)** escolhe o trecho e passa para o **Agente 5 (editor)**. O editor monta um plano de edição e exporta o vídeo. Depois o **Agente 4 (diretor)** dá a nota. Aprovado, o vídeo segue para o **Agente 2 (postagem)**.
- **Corte manual do site e vídeo importado** vão direto para o diretor. Se ele pedir, o editor corrige: tira pausas, ajusta o começo e o fim, normaliza o volume e muda o enquadramento.
- **Agente 3 (criação)** passa por duas notas. A primeira é das **cenas e do roteiro**, e o Agente 3 refaz só as cenas apontadas. A segunda é do **vídeo final**. Depois disso o vídeo vai para a sua aprovação.

## Regra fixa

- **Aprovação:** nota 70 ou mais **e** nenhum bloqueio. Nota alta nunca passa por cima de bloqueio.
- **Correções:** a primeira avaliação não conta. Cada etapa tem até **5 correções**: uma para as cenas e outra para o vídeo final, com contadores separados. Na 5ª correção reprovada, a execução vai para **"Precisa da sua revisão"**.
- **Correção que não muda nada:** se o plano e o arquivo continuam iguais, a esteira para e não gasta as 5 tentativas.
- **Falha técnica:** se o FFmpeg cai ou falta espaço, a fila tenta de novo, e isso **não** conta como correção.
- **Certificado:** o certificado do diretor é assinado pelo servidor e vale só para o SHA-256 daquele arquivo. Exportou de novo, o diretor confere de novo. O Agente 2 confere o certificado ao criar o post e de novo na hora de postar.
- **Sua revisão:** você pode liberar um vídeo com nota baixa, e o seu motivo fica registrado. **Não** pode liberar bloqueio de direitos, arquivo quebrado, áudio faltando nem outro bloqueio técnico.

## Como a nota é feita

A nota é medida no arquivo exportado, em uma passada do FFmpeg pelo vídeo inteiro. Ela procura tela preta, imagem travada, silêncio, volume, erro de decodificação, buracos no tempo, formato da tela, legenda, começo e fim de frase, e duração. A opinião de IA **nunca muda a nota** e nunca bloqueia.

| Vídeo final | Pontos |
|---|---|
| Técnica, som e sincronia | 20 |
| Legendas e áreas seguras | 15 |
| Imagem e enquadramento | 15 |
| Ritmo | 15 |
| Gancho (começo) | 15 |
| Começo e fim completos | 10 |
| Identidade e template | 10 |

| Cenas e roteiro (Agente 3) | Pontos |
|---|---|
| Estrutura | 20 |
| Roteiro | 20 |
| Continuidade | 20 |
| Narração e falas | 15 |
| Imagens e direitos | 25 |

**Bloqueios:** arquivo quebrado, vídeo que trava, falta de áudio, som fora de sincronia, formato errado, tela preta no meio, fala cortada no começo ou no fim, e direitos não confirmados.

## Editor (Agente 5) e segurança

O plano de edição aceita só uma lista fechada de efeitos: zoom, enquadramento, fade, legenda e volume. Todos os números ficam presos em faixas seguras. As correções que o diretor pode pedir também são uma lista fechada: ajustar o começo, ajustar o fim, tirar uma pausa, aumentar a legenda, subir a legenda, reduzir o zoom, normalizar o volume, trocar o enquadramento, suavizar os cortes e refazer cenas. **Nenhum texto de IA vira comando do FFmpeg.** Os trechos que você travar não são mexidos.

## Programação diária (Agente 2)

Fica em **Agentes > 2 · Programação diária**. Cada conta e rede tem a sua programação:

- **Fixo:** cada horário é um post. A meta do dia é a quantidade de horários.
- **Automático:** você diz quantos posts por dia, e eles são espalhados na janela com o intervalo mínimo. Se não couber, o formulário avisa.
- **Misto:** horários fixos mais alguns flexíveis.

Você também escolhe os dias da semana, pode ter horários diferentes por dia e pode pausar datas especiais. A prévia mostra os próximos 7 dias com datas reais, no fuso `America/Sao_Paulo`.

Um horário só recebe vídeo **com certificado válido para o arquivo atual** e sem bloqueio de direitos. Sem vídeo aprovado, o horário fica vazio: nada é repetido para tapar buraco. A chave de cada horário é `conta:rede:data:hora`, então reiniciar o servidor não duplica nada.

Se o servidor estava desligado na hora de um post, o padrão é **não postar atrasado**. Esse post vai no próximo horário. Também dá para escolher "postar quando voltar, até um atraso máximo" ou "esperar você".

Os posts que você agendou à mão continuam como estão. O Kwai fica como lembrete manual.

## Ferramentas (Skills > Ferramentas dos agentes 4 e 5)

O servidor só **detecta** o FFmpeg, o VMAF, o Auto-Editor e a chave do YouTube. Nada é instalado sozinho.

O MCP Video e o Remotion não foram adotados:

- O **MCP Video** repete o que o FFmpeg daqui já faz.
- O **Remotion** precisa de Node e Chromium e tem uma licença comercial que precisa de revisão.

O VMAF não entra na nota. Ele só serve para comparar duas versões do **mesmo** trecho e não mede viralização.

## Referências virais

As referências vêm de duas fontes: os vídeos públicos do tema no YouTube (com a chave e dentro da cota) e os seus próprios números, do painel Aprendizado. Sem dados, a resposta é "dados insuficientes". As referências viram observação no relatório e **não mudam a nota**.

## Rotas

- `GET /api/v1/pipeline` e `PUT /api/v1/pipeline/chave`
- `GET /api/v1/pipeline/jobs`, `GET /api/v1/pipeline/jobs/{id}`, `GET .../history` e `POST .../manual-review`
- `GET /api/v1/quality/reports/{id}` e `GET /api/v1/quality/policy`
- `GET /api/v1/capabilities` e `GET /api/v1/viral/references?topic=`
- `GET|POST /api/v1/agent2/schedules`, `GET|PATCH|DELETE /api/v1/agent2/schedules/{id}` (o PATCH pede `version`) e `POST .../preview`
- `POST /api/v1/agent2/preview`, `GET /api/v1/agent2/slots`, `PATCH /api/v1/agent2/slots/{id}` (cancelar), `POST /api/v1/agent2/run` e `GET /api/v1/agent2/metrics`

## Testes

```
cd servidor
PYTHONPATH=. python3 testes/teste_pipeline_5_agentes.py   # regra 70/5, certificado, plano, editor<->diretor com vídeos de verdade
PYTHONPATH=. python3 testes/teste_agenda_agente2.py       # programação diária, fuso, horário perdido, corte manual pela esteira
PIPELINE_V2=1 PYTHONPATH=. python3 testes/teste_agente3.py  # Agente 3 inteiro com a esteira ligada
```
