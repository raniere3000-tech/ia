# CHECKPOINT — Agente 6: autonomia e integração de capas

Checkpoint próprio desta frente. **Não substitui** o `ESTADO_ATUAL.md` (checkpoint principal do EstúdioClip 2.0, que continua apontando a retomada da Fase 2 em F2.01).

```yaml
frente: AGENTE6_AUTONOMIA_CAPAS
branch: codex/agente6-autonomia-capas
sha_origem: 222a1c399da1e2d081fda16de2faa4a3cf092b7a
microetapa_atual: TH.08
status: CONCLUIDA
proxima_microetapa: VALIDACAO_FINAL_NO_CELULAR
merge: NAO_REALIZADO
producao: NAO_PUBLICADA
publicacoes_reais_em_teste: NENHUMA
```

## Configuração aprovada pelo dono (24/11/2026)

Modo automático · 3 capas por vídeo · nota mínima 70 · até 5 correções por etapa · geração e seleção automática · correção automática · recuperação após o vídeo mudar · pessoa só nas exceções · exigir capa válida antes de publicar · bloquear capa desatualizada · repetir envio de capa sem duplicar post · aprender com métricas reais quando houver · controle manual continua disponível.

## TH.01 — Auditoria técnica (concluída)

Baseline nesta branch (antes de mudar nada): `teste_thumbnails` 101 ok · `teste_redes_independentes` 13 ok · `teste_esteira_7` 70 ok · `teste_coordenador` 80 ok.

Problemas confirmados no código (SHA 222a1c3):

| # | Problema | Onde | Evidência |
|---|---|---|---|
| 1 | Modo padrão do A6 é supervisionado | `thumbnails.py` `CONFIG_PADRAO['modo']` | `'modo': 'supervisionado'` |
| 2 | Depois de refazer uma capa, a seleção automática não roda | `thumbnails.job_thumbnail` (fim) | `elif cfg['modo'] == 'automatico' and not refazer_n:` |
| 3 | Coordenador conclui a tarefa de capas com capa ainda esperando escolha | `coordenador.py` `a6.capas` | `if j['estado'] in ('aguardando_escolha', 'pronto', 'revisao_manual'): ... 'concluida'` |
| 4 | Varredura ignora vídeo que já tem qualquer pedido (mesmo de versão antiga, falho ou cancelado) | `thumbnails.varrer` | `cand = [f for f in fontes(...) if not f['job'] and ...]` |
| 5 | Vídeo mudou → escolha cai e o pedido fica "aguardando escolha" para sempre (ninguém pede capa da versão nova) | `thumbnails.revalidar` + item 4 | `'O vídeo mudou: peça capas para a versão nova.'` |
| 6 | A2 só exige capa no YouTube, e a opção vem desligada | `postagem.conferencia` | `if rede == 'youtube': ... th.config()['exigir_capa_youtube']` (padrão `False`) |
| 7 | Falha no envio da capa vira só uma nota; sem estado por rede, sem nova tentativa, sem reaproveitar o ID do vídeo já postado | `postagem._capa_youtube` | `_nota_capa(p, 'youtube', 'O YouTube não aceitou a capa ...')` |
| 8 | TikTok/Instagram recebem só o segundo de um quadro original; a arte com texto nunca vai | `postagem.postar_tiktok` / `postar_instagram` | `video_cover_timestamp_ms` / `thumb_offset` = `quadro_t` |
| 9 | Dois mecanismos de capa: `publish_package.sugerir_capas` (3 quadros por corte, escolha manual) e o Agente 6 | `publish_package.py` | pacote do A2 tem `capas`/`capa_escolhida` próprios |
| 10 | Esteira e Coordenador podem pedir capas do mesmo vídeo com chaves diferentes | `esteira._a6` (`esteira:<id>:<sha>`) e `coordenador` (`coord:<tarefa>:<n>`) | pedidos redundantes para o mesmo `video_sha` |

Capacidade real das APIs (sem envio real nesta auditoria):
- **YouTube**: `thumbnails.set` aceita JPEG até 2 MB para conta verificada; pode ser chamado de novo depois, só com o `videoId` (não reenvia o vídeo).
- **TikTok**: Direct Post aceita `video_cover_timestamp_ms` (um quadro do próprio vídeo). Sem app aprovado o envio é assistido (rascunho) e a capa é escolhida no app.
- **Instagram Reels**: `thumb_offset` (milissegundo do vídeo); `cover_url` exige imagem em URL pública (o servidor no Termux não tem URL pública fixa) — não usado.
- **Facebook / Kwai**: sem capa pela integração atual; fica manual.

## TH.02 — Autonomia e seleção automática (concluída, 41f97b7)

- `thumbnails.CONFIG_PADRAO`: modo automático, capa obrigatória (todas as redes), recuperação, reenvio da capa, estratégia por rede.
- Migração única `agente6.autonomia_v1`: aplica a configuração aprovada uma vez; depois a escolha feita na tela vale.
- `selecionar_melhor`: escolhe a aprovada de maior nota; roda também depois de refazer; nunca troca uma escolha sua válida.
- `exige_capa(rede)`: regra única usada pelo Agente 2 (TH.05).

## TH.03 — Correção e recuperação (concluída, 39cec86)

- `diagnosticar` / `recuperar(simular)`: vídeo mudou → pede capa da versão nova; pedido falhou → refaz com outro método até `max_recuperacoes`, depois vira exceção; aprovada sem escolha → escolhe (automático) ou pendência (supervisionado); cancelado por você é respeitado. `varrer` usa a recuperação.
- `teste_coordenador` passa a fixar o modo supervisionado (cobre o caminho manual de escolher a capa na liberação).

## TH.04 — Integração A4/A5/A6/A7 (concluída, 17c8ba3)

- `criar(..., reaproveitar=True)`: esteira e Coordenador usam o mesmo pedido vivo da mesma versão do vídeo (problema 10).
- Coordenador no automático só conclui "Fazer as capas" com capa escolhida e válida (problema 3); sem aprovada → pendência sua.
- Esteira escolhe a aprovada sozinha no automático.
- `video_com_capa(arq)`: versão de publicação com a arte como quadro final de 0,5 s (não mexe no gancho). Fica em `thumbnail_embutidos` presa à MESMA escolha; o vídeo liberado pelo A7 não muda e o derivado não vira vídeo novo para o A6 (sem ciclo). Escolha revogada → o derivado perde a capa.
- Banco: migração 14 (`thumbnail_embutidos`, `thumbnail_aplicacoes`). **Atenção no merge**: se a Fase 2 também criar a migração 14 em `banco.py`, renumerar uma das duas.

Testes TH.04: `teste_agente6_autonomia` 33 ok · `teste_thumbnails` 102 ok · `teste_coordenador` 80 ok · `teste_esteira_7` 70 ok · `teste_redes_independentes` 13 ok.

## TH.05 — Agente 2 (concluída, dd5cea2)

- `conferencia` usa `th.exige_capa(rede)` em todas as redes; capa de versão antiga não vale (hash do arquivo).
- Estado da capa por post/rede em `p['redes'][rede]['capa']` e `thumbnail_aplicacoes`: aplicada (rede confirmou), indicada (rede aceitou o tempo do quadro), falhou (tenta de novo), bloqueada (403), manual (no app), sem_capa.
- YouTube: falha da capa não derruba o post; `reenviar_capa` / `reenviar_capas_pendentes` mandam SÓ a capa pelo ID do vídeo (espera 5→15→60→180→720 min, até `max_envios_capa`).
- TikTok/Instagram: sobem a versão com a arte no quadro final (`video_com_capa`) e mandam o tempo dele; TikTok assistido fica "manual" com instrução do último quadro.

## TH.06 — Estoque (concluída, 947ee00)

- `auditar_estoque(aplicar)`: redundantes cancelados ("Redundante: ..."), recuperação, posts travados por falta de capa voltam à fila (mesmo post), YouTube já postado recebe só a capa; outras redes listadas como manuais. Simular não muda nada.
- `ignorar`: você tira um vídeo da recuperação automática.
- API: `GET /api/v1/thumbnails/autonomia`, `POST .../autonomia/auditar|ignorar|reenviar-capa`.

## TH.07 — Tela (concluída, 1d9b7a5)

- `frontend/src/pages/ThumbAutonomia.tsx`, aba "Autonomia e Integração" em Agentes > Agente 6 (o "Configurar" do cartão abre aqui). Conferida no navegador (1440 e 390 px) com o servidor de teste: sem erro no console e sem rolagem lateral. Não vista no celular real.

## TH.08 — Regressão (concluída, 8969314)

- Suíte inteira do servidor (61 arquivos): todos passam, menos:
  - `teste_agente3` (2 falhas, `KeyError: 'imagem'`): **igual na origem 222a1c3**, não é desta frente;
  - `teste_email` (pede digitação) e `teste_trecho_link` (falta `yt_dlp` nesta máquina): ambiente.
- Ajustados para a nova configuração (sem mudar o que testam): `teste_thumbnails`, `teste_coordenador`, `teste_decisoes` (modo supervisionado), `teste_liberacao`, `teste_versao_refeita` (capa obrigatória desligada).
- `teste_agente6_autonomia` 72 ok. Frontend: `npm run build` ok, `npm test` 16 ok.

## Pendências (não feitas nesta frente)

- Não testado no celular nem com contas reais (nenhuma publicação real foi feita).
- "Aprender com métricas reais": nada novo; continua o aprendizado que já existe (`desempenho`, escolhas por layout). Ligar nota da capa a CTR real depende de métrica do YouTube Analytics.
- `publish_package.sugerir_capas` (3 quadros do pacote do A2) continua existindo em paralelo: não foi removido para não quebrar telas antigas.
- Migração 14 do banco: conferir conflito com a Fase 2 no merge.

## Plano das microetapas (histórico)

- **TH.02** modo automático por migração única (respeita quem já escolheu manual), seleção automática também depois de refazer.
- **TH.03** varredura de recuperação: versão nova do vídeo, pedido falho/cancelado, aguardando escolha com aprovada.
- **TH.04** Coordenador só conclui com capa escolhida e válida; esteira sem pedidos duplicados; quadro da capa embutido no vídeo vinculado à mesma escolha (sem novo ciclo).
- **TH.05** A2: capa obrigatória por rede, estado da capa por rede separado do post, nova tentativa só da capa no YouTube.
- **TH.06** auditoria e recuperação do estoque (simular e aplicar).
- **TH.07** tela "Autonomia e Integração de Capas" em Agentes → Agente 6.
- **TH.08** testes novos + regressão.

## Como retomar

```bash
git fetch origin codex/agente6-autonomia-capas && git checkout codex/agente6-autonomia-capas
cat ESTADO_ATUAL_AGENTE6.md
cd servidor && PYTHONPATH=. python3 testes/teste_agente6_autonomia.py && PYTHONPATH=. python3 testes/teste_thumbnails.py
```
