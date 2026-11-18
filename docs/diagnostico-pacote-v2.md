# Diagnóstico: pacote unificado v2 contra o que existe

Data: 18/11/2026. Base conferida: branch `main` no commit `519decd`.

Legenda:
- **Pronto:** existe no servidor, tem teste e aparece na tela.
- **Parcial:** existe, mas falta uma parte do pedido.
- **Falta:** ainda não existe.

## 3. Interface

| Pedido | Situação | Onde |
|---|---|---|
| Central de Automação com 6 abas | Pronto | `pages/Central.tsx` (`#central`) |
| Indicadores: postagens, estoque, rodando, revisão, falhas | Pronto | `orquestrador.resumo` |
| Simular, pausar e retomar | Pronto | `/api/v1/automacao/*` |
| "Gerar sugestões com IA" e "Comparar alterações" | Parcial | Sugestões por regra existem. Falta a IA sugerir mudanças, mostrar a diferença e respeitar o cadeado |
| Prévia de impacto antes de salvar | Falta | |
| Origem do conteúdo (cortes, originais ou mix) | Falta | |
| Orçamento diário e semanal | Falta | O limite existe por vídeo, no produtor |

## 3.3 Cartões dos agentes

| Pedido | Situação |
|---|---|
| **Agente 1:** estoque mínimo e alvo, sem pesquisa desnecessária | Pronto |
| **Agente 1:** frequência por estoque, agenda ou híbrido | Falta. Hoje é só estoque ou meta semanal |
| **Agente 1:** máximo de fontes por rodada | Falta. Hoje é 1 vídeo por rodada |
| **Agente 2:** programação por conta e rede, fixo, automático ou misto, fuso, horário perdido | Pronto (`agenda_postagem.py`) |
| **Agente 2:** prioridade por linha de conteúdo | Falta |
| **Agente 2:** editar um horário sozinho | Parcial. Só dá para cancelar |
| **Agente 3:** linhas, lotes e produção contínua | Pronto (`linhas_conteudo.py`) |
| **Agente 3:** criar a linha a partir de uma descrição livre | Falta. O formulário tem campos, mas a IA não preenche |
| **Agente 3:** horários da linha | Parcial. A linha usa a programação da rede; falta criar o horário dentro da linha |
| **Agente 4:** nota 70, 5 correções por etapa, revisão manual, certificado preso ao arquivo | Pronto (`pipeline.py`, `diretor_qualidade.py`) |
| **Agente 4:** comparativo antes e depois | Parcial. Todas as notas aparecem, mas sem a diferença entre elas |
| **Agente 5:** plano de edição validado e lista fechada de correções | Pronto (`editor_ia.py`, `contratos.py`) |
| **Agente 5:** modo supervisionado (você aprova o plano antes) | Falta |

## 4. Fábrica de conteúdo

| Pedido | Situação |
|---|---|
| Pautas com fontes, classificação e checagem de repetição | Pronto |
| "Gerar mais", "Trocar", "Bloquear" e "Aceitar" | Pronto |
| Afirmação científica sem fonte não aparece como fato | Parcial. Hoje o servidor só vê se a página abre; falta conferir a afirmação contra o texto da fonte |
| Biblioteca Criativa: modelos de roteiro, pacotes visuais e perfis de narração com versões e travas | Falta. Personagens e cenários já existem (`series.py`) |
| Orçamento da linha | Falta. O campo é guardado, mas não segura gasto |

## 5. Orquestrador e estoque

| Pedido | Situação |
|---|---|
| Estoque, reservado, em produção previsto, déficit e histerese | Pronto |
| Um vídeo em várias redes conta como um ativo | Pronto (chave `sha:rede`) |
| Simulação sem gravar nada | Pronto (testado) |
| Recalcular depois de postar | Pronto: o ciclo roda a cada 5 min e o Agente 2 a cada 3 min |

## 6. Fluxos e regras

- **Pronto:** fluxo A (cortes) e fluxo B (originais) pela esteira.
- **Pronto:** contadores separados para erro técnico e para correção.
- **Pronto:** aprovação presa ao arquivo; editar invalida a aprovação.

## 7. Ferramentas externas

| Ferramenta | Situação | Por quê |
|---|---|---|
| FFmpeg | Em uso | Motor de tudo |
| Auto-Editor | Só é detectado | Falta o adaptador opcional, com o FFmpeg como alternativa |
| VMAF | Só é detectado | Não mede viralização |
| Remotion, MCP Video | Não adotados | Precisam de Node e Chromium; licença |
| MoneyPrinterTurbo, OpenReels, CueSync, YT FactCheck, QC Video e as outras da tabela 7.2 | Não integradas | O arquivo exige ler o LICENSE de cada uma e fazer um teste antes. Nada é instalado sem você escolher |
| Ficha de cada ferramenta (repositório, commit, licença, licença conferida, sistema, custo, teste, alternativa, ligada) | Falta | Será a tela "Ferramentas" |

## 10. Aceite final

> Criar uma linha de 6 vídeos a partir de uma descrição, acompanhar produção e correções, conferir os vídeos renderizados e ver no calendário os arquivos aprovados nos horários, sem duplicar nem postar sem autorização.

Hoje falta a parte "a partir de uma descrição". Também falta um teste que faça o caminho inteiro de uma vez: 6 renders reais, diretor, aprovação e calendário.

## O que foi feito (18/11)

Todos os 9 itens abaixo foram feitos, cada um com teste.

1. **Linha a partir de descrição.** A IA monta a proposta e a tela mostra campo por campo. Nada é gravado antes de você salvar. Campos com cadeado não mudam, e estilo beta ou indisponível vira aviso. A linha tem horários e dias próprios, que entram na programação diária de cada rede.
2. **Checagem de fatos.** A IA cita um trecho e o servidor procura esse trecho no texto baixado da fonte. Afirmação de saúde, dinheiro ou lei sem confirmação vai para você. O que não foi confirmado entra no roteiro como "não apresentar como fato".
3. **Biblioteca Criativa.** Tem modelos de roteiro, pacotes visuais e perfis de narração. Cada mudança vira uma versão nova, e os campos podem ter cadeado. O episódio guarda a versão que usou.
4. **Agente 2.** A prioridade de 1 a 5 da linha decide quem ocupa o horário. Você pode mudar um horário só naquele dia: o post vai junto e o intervalo mínimo é respeitado. Cada horário mostra o nome do vídeo.
5. **Agente 1.** Pode trabalhar pelo estoque, pela meta da semana ou pelos dois. Também dá para escolher quantas fontes ler por rodada, de 1 a 5.
6. **Orçamento da linha.** Tem um limite por dia, calculado com o custo estimado das últimas 24 h, e um limite por vídeo.
7. **Editor e diretor.** O editor tem três modos: automático, supervisionado (você dá o ok final) e manual. Cada relatório mostra a diferença de nota para a avaliação anterior.
8. **Ferramentas externas.** Cada ferramenta tem uma ficha com licença, sistema, custo e alternativa. Só liga com a licença conferida por você e o teste passando neste aparelho. O adaptador do Auto-Editor é opcional e **não foi testado com o programa de verdade**, porque a instalação não foi permitida neste ambiente. Sem ele, o FFmpeg continua sendo usado.
9. **Teste de aceite** (`testes/teste_aceite_linha6.py`, 44 ok). O teste usa o servidor HTTP de verdade e simula o Gemini.
   - Descrição → proposta → linha salva com 3 horários em 2 redes.
   - 6 pautas e lote de 6.
   - 6 MP4 diferentes renderizados pelo FFmpeg, cada um com nota e certificado do diretor para o SHA exato.
   - Aprovação automática da linha.
   - 12 horários ocupados, 6 vídeos em 2 redes, sem repetir vídeo na mesma rede.
   - Nada publicado.

**Correção pedida:** os botões da Central estavam sem cor (apareciam em branco). Agora todos têm o estilo normal, e há uma regra de segurança no CSS.

**Mudança de comportamento:** a publicação automática de uma linha agora vale mesmo com a Central desligada. Ela ainda exige o certificado do diretor, e não vale com a Central pausada. Depois de uma aprovação, o Agente 2 confere os horários na hora, sem esperar os 3 minutos do relógio.

**Não testado no celular.** O Gemini, o YouTube e as redes de verdade também não foram usados no teste.
