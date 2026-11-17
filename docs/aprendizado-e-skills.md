# Aprendizado dos agentes e skills novas (17/11/2026)

## Skills (Etapa E)
- 15 skills novas no `servidor/skills/manifesto.json` (versão 2, 133 no total). Cada uma tem commit fixado, SHA256 do SKILL.md, tamanho e licença MIT lida do arquivo LICENSE do repositório no mesmo commit.
- Só o SKILL.md entra. Os scripts das skills (`hookscore.py`, `swipe.py`, `deadair.py`, `title.py`, `retention.py`, `scripts/` do `video-highlight-skill`) **não são instalados nem executados**. As skills que os citam ficam como `runtime-auditar`.
- O filtro de texto (`skills/seguranca.py`) agora também descarta linhas que citam o serviço externo WoopSocial, comandos `python`, arquivos `.py` e pastas `scripts/`.
- `yt-viral` é texto corrido, sem regras em lista: fica instalada, mas o roteador a deixa de fora e diz o motivo.
- Perfis novos do roteador: `agente1.gameplay`, `radar.viralidade`, `agente3.ganchos`, `diretor.storyboard_visual`, `site.estilos_cortes`, `perfil.canal`, `agente2.pacote`, `agentes.aprendizado`.
  Usados de verdade: gameplay (pedido dos ganchos), radar (pedido das ideias), ganchos (roteiro do Agente 3), pacote e storyboard visual (lista de boas práticas para a pessoa conferir), aprendizado (painel).
  Só consulta, sem uso automático ainda: `site.estilos_cortes`, `perfil.canal`.
- Para desligar um perfil sem apagar nada: aba Skills do site → perfil → Desligar (ou Desfazer).

## Aprendizado dos agentes (`servidor/aprendizado.py`)
- Tabelas novas (migração 6, só acrescenta): `aprendizado_snapshots`, `aprendizado_importacoes`, `aprendizado_pesos`, `aprendizado_experimentos`.
- Retratos: um por corte medido em cada rede (ou por linha importada). Têm fonte, rede, período e hash; não se editam, só se apagam.
- Mínimo de 5 vídeos medidos por valor. Abaixo disso: "dados insuficientes".
- Pesos só valem no sorteio de estilo do Agente 1. Cada aplicação é uma versão; "Desfazer" volta à anterior ou ao sorteio igual.
- Apagar dados (tudo, rede ou uma importação) refaz os pesos: se não sobrar amostra, o peso é desligado.
- Teste A/B: uma variável por vez, as outras fixas, só um teste ativo. Com teste de estilo ativo, o Agente 1 sorteia só entre A e B.
- Nunca mexe em frequência ou horário de postagem. Nada daqui posta ou aprova.
- Rotas (senha do servidor): `GET /agente/aprendizado`, `POST /agente/aprendizado/{importar,capturar,apagar,aplicar,desfazer,experimento,experimento/encerrar}`.
- Como voltar atrás: botão Desfazer (pesos), Encerrar (teste), Apagar (dados). Tudo fica no registro de eventos (`ator = aprendizado`).
- Não testado no celular; testado no servidor de teste e no navegador.
