# EstúdioClip 2.0 — Fase 0: auditoria e baseline

**Data:** 24/11/2026  
**Base auditada:** `main` em `b948059ad7c88a13bd7750623298f087fed75a2d` (merge do PR #17, 24/11/2026 08:42 -03)  
**Onde foi feito:** ambiente de nuvem (Linux, Python 3.13.18, FFmpeg do sistema, Node 22). **Não** foi feito no celular Termux.  
**Regra desta fase:** só leitura e testes. Nenhum código, dado, banco, flag ou agendamento foi alterado. Este arquivo é a única mudança do PR.

> Legenda usada em todo o documento  
> **PRESENTE** = existe no código. **FUNCIONA (teste)** = teste automático passou aqui, com redes/IA simuladas.  
> **FALHA** = teste falha ou o código faz o contrário do que a arquitetura pede. **NÃO VERIFICADO** = depende do celular, de conta real ou de API real.  
> Nada marcado como FUNCIONA (teste) foi validado em produção.

---

## 1. Ambiente e versões

| Item | Valor | Situação |
|---|---|---|
| Repositório | `raniere3000-tech/ia`, branch `main` | conferido |
| SHA base | `b948059` | conferido |
| Versão declarada do servidor | `VERSAO = '2.0.0'` (`servidor/servidor.py:42`) | conferido no código |
| Banco | SQLite em `~/.estudioclip/database/studio.sqlite`, WAL, 13 passos de migração (`banco.ESQUEMA`), 69 `CREATE TABLE` | conferido no código |
| Outros armazenamentos | JSON: `posts.json`, `contas.json`, `ritmo_posts.json` (postagem.py); estado do Agente 1 em JSON próprio | conferido no código |
| Backup antes de migrar | `banco.migrar()` copia o banco para `studio-antes-vN.sqlite` antes de mudar o esquema | PRESENTE |
| Backup/restauração manual | `servidor/backups.py` (`fazer`, `listar`, `testar_restauracao`) | PRESENTE; ensaio no celular NÃO VERIFICADO |
| Frontend | React/Vite, GitHub Pages pelo workflow `pages.yml` (push na main) | build OK aqui |
| Servidor real (Termux) | branch `main` em `b948059` (mesmo SHA auditado); armazenamento 109 GB, 29 GB usados, 79 GB livres (28%) | **conferido por você em 24/11 10:18**; versão do esquema do banco real e backup ainda NÃO VERIFICADOS |
| Pasta `backend/` (FastAPI) | código antigo, não usado pelo site | legado; não apagar sem decisão |
| `docs/estado-e-proximos-passos.md` | descreve o MVP antigo ("publicação ainda não desenvolvida") | **desatualizado** |

## 2. Baseline da suíte de testes

Comando (cada arquivo isolado, com pasta temporária própria):

```
cd servidor && PYTHONPATH=. python3 testes/<arquivo>.py
cd frontend && npx tsc --noEmit -p . && npm run build && npm test
```

Resumo: **52 arquivos `teste_*.py` → 43 PASS, 7 FAIL, 2 não rodam neste ambiente.** Frontend: tsc PASS, build PASS (aviso de bloco > 500 kB), `npm test` 16/16 PASS.

| Teste | Resultado | Observação |
|---|---|---|
| teste_3d, teste_aceite_linha6 (44), teste_agenda_agente2 (45), teste_alertas (10), teste_aprendizado (47), teste_busca_canais (13), teste_cancelamento, teste_comparacao (65), teste_criativo (55), teste_custo_corte (57), teste_decisoes (30), teste_diretor (44), teste_esteira_7 (70), teste_esteira_corte_salvo (7), teste_estilos_agente1 (6), teste_estilos_editar (74), teste_estilos_visuais (65), teste_exportacao (23), teste_ffmpeg_tempo (8), teste_gameplay (34), teste_gancho_capa, teste_kwai_diario (43), teste_liberar_corte (10), teste_link_original (24), teste_live (47), teste_motor (50), teste_pacote (23), teste_painel (34), teste_perfis (21), teste_pipeline_5_agentes (51), teste_publicacao_lotes, teste_redes_independentes (13), teste_reposicao (33), teste_serie_completa (16), teste_site_lote1 (30), teste_skills (57), teste_skills_novas (28), teste_temas (12), teste_thumbnails (101), teste_tiktok_assistido (36), teste_versao_refeita (10), teste_whatsapp (12) | **PASS** | número entre parênteses = verificações "ok" |
| teste_agente3 | **FAIL** (4 verificações) | produção do Agente 3 para em "limite de gasto R$ 2,00 seria passado" |
| teste_central_automacao | **FAIL** (3 + erro) | vídeo com certificado não vira publicação; termina em `StopIteration` |
| teste_comandos | **FAIL** (5) | comandos do WhatsApp: "não está esperando a sua aprovação" |
| teste_coordenador | **FAIL** (3 + erro) | pacote não é liberado: "Falta concluir a conferência do diretor" |
| teste_descricao | **FAIL** (erro) | `ErroAprovacao 409: Falta o parecer favorável do diretor para esta versão` |
| teste_liberacao | **FAIL** (erro) | mesmo erro 409 do diretor |
| teste_skills_agentes | **FAIL** (erro) | `KeyError: 'redes'` em `postagem.conferencia` (postagem.py:1084) |
| teste_email | não roda aqui | é interativo (pede e-mail e senha pelo teclado); não é teste automático |
| teste_trecho_link | não roda aqui | precisa de `yt_dlp` instalado |

### Desde quando falham (rodado em commits antigos, um teste por vez)

| Commit | Data | Os 7 testes acima |
|---|---|---|
| `36ec6d1` | 22/11 17:44 | **todos PASS** |
| `cdda997` "Revisar cada etapa e refazer o vídeo até o diretor aprovar" | 22/11 18:36 | teste_agente3, teste_central_automacao, teste_comandos, teste_coordenador, teste_descricao e teste_liberacao já **FAIL** (teste_skills_agentes ainda PASS) |
| `18b7382` "Reutilizar o post e impedir envios duplicados" | 22/11 18:58 | primeiro commit em que teste_skills_agentes falha (achado por bisect) |
| `8823ca2` (main antes do PR #17) | 23/11 | **todos FAIL** |
| `b948059` (main atual, com PR #17) | 24/11 | **todos FAIL** (mesmos erros) |

**Conclusão:** as 7 falhas **não vieram do PR #17**. Seis delas começaram no commit `cdda997`, que trouxe a regra nova do diretor (`aprovacoes.diretor_ok`, cdda997): agora a aprovação exige parecer do diretor para o SHA exato do arquivo, e os testes antigos não criam esse parecer. Falta decidir, na Fase 1, se o certo é atualizar os testes (regra nova correta) ou ajustar o código (regra bloqueando fluxos que deviam passar, como comandos do WhatsApp e liberação do Coordenador). O `KeyError: 'redes'` é um defeito de código: `conferencia()` não aceita post sem o campo `redes`.

## 3. Inventário por módulo

### Agentes

| Módulo | Onde | Situação | Evidência / observação |
|---|---|---|---|
| A1 Cortes: busca de vídeos, prioridade por canal aprovado → legenda → views | `agente.py:627-680` | PRESENTE · FUNCIONA (teste) | `priorizar_legendas` só ordena; não exclui vídeo sem legenda |
| A1 sem legenda: transcrição pela IA | `agente.py:1497-1500`, `transcrever_ia` | PRESENTE · NÃO VERIFICADO real | com menos de 40 palavras de legenda, transcreve o áudio pelo Gemini; sem fala usa som e imagem |
| A1 retentativa da **mesma fonte** | `agente.py:2026-2031`, `servidor.py:958` | **FALHA** frente à arquitetura | qualquer erro (inclusive de rede) marca o vídeo como "visto" com `erro:` e a próxima rodada pega **outro vídeo**; o job do A1 é enfileirado com `max_tentativas=1`. Bate com o relato "troca indevida de fonte" |
| A1 gancho íntegro | `diretor_qualidade.avaliar_previo_corte`, `editor_ia.corrigir` | PRESENTE · FUNCIONA (teste) | A4 confere começo/fim antes de renderizar; sem teste com fala real |
| A3 Criação IA (roteiro → cenas → voz → montagem) | `produtor.py`, `storyboard.py`, `series.py`, `rig2d.py`, `personagens3d.py` | PRESENTE · **FALHA** no teste | teste_agente3 para no limite de gasto desde cdda997 |
| A4 Diretor (pré e pós) | `diretor_qualidade.py`, `qualidade.py`, `aprovacoes.diretor_ok` | PRESENTE · FUNCIONA (teste) | laudo preso ao SHA; detecta tela preta/congelada (`blackdetect`/`freezedetect`) |
| A5 Editor (plano de edição e render) | `editor_ia.py` (`plano_do_corte`, `executar_corte`), `estilos_codigo.py`, `renderizador.py`, tabela `edit_plans` | PRESENTE · FUNCIONA (teste) | existe plano com versão e hash. **Não existe** registro "efeito planejado x efeito aplicado no arquivo" (item 4 do aceite) |
| A6 Capas | `thumbnails.py`, tabelas `thumbnail_*` | PRESENTE · FUNCIONA (teste, 101 ok) | refazer por variante e seleção presa ao `video_sha` (`thumbnails.py:1123,1145`). Não há ação explícita de **rejeitar** uma capa |
| A7 Coordenador | `coordenador.py`, tabelas `coordenador_*` | PRESENTE · **FALHA** no teste | liberação do pacote bloqueada pela regra do diretor (teste_coordenador) |
| Esteira obrigatória dos 7 agentes | `esteira.py`, `rotas_esteira.py`, tabelas `esteira_*` | PRESENTE · FUNCIONA (teste, 70 ok) | ligada por padrão; nunca testada no celular |
| A2 Postagem por rede | `postagem.py`, `agenda_postagem.py`, `publicacao_lotes.py` | PRESENTE · FUNCIONA (teste) | status independente por rede (13 ok), lotes com pausa/limite (ok). **Contas reais NÃO VERIFICADAS** |
| A2 TikTok assistido | `tiktok_assistido.py` | PRESENTE · FUNCIONA (teste, 36 ok) | assistido por padrão; Direct Post só com aprovação do app. Não confunde com publicação direta |
| A2 Kwai diário | `kwai_diario.py` | PRESENTE · FUNCIONA (teste, 43 ok) | manual por natureza |

### Infraestrutura e transversais

| Módulo | Onde | Situação | Observação |
|---|---|---|---|
| Fila durável | `fila.py`, tabela `jobs` | PRESENTE · FUNCIONA (teste) | estados `agendado/na_fila/aguardando_tentativa/rodando/concluido/falhou/cancelado`, aluguel de 180 s como sinal de vida, esperas 60/300/1200 s, retomada após reinício |
| Cancelamento | `fila.cancelar`, `agente.verificar_cancelamento`, FFmpeg cancelável | PRESENTE · FUNCIONA (teste) | cancelamento cooperativo; não testado em todas as etapas do aceite (criação, aprovação, coleta) |
| Pausa/retomada/tentar de novo | `fila.pausar/retomar/tentar_de_novo` | PRESENTE | sem teste por etapa |
| Estados da arquitetura (`CREATED`… `ANALYZED`) | — | **AUSENTE** | estados atuais estão em português e espalhados (fila, esteira, pipeline_runs). Mapeamento fica para a Fase 1 |
| Vertente `track` (CUTS / AI_ORIGINAL) | — | **AUSENTE** | "origem" corte/projeto existe na esteira, mas não há campo `track` imutável |
| Aprovação por versão | tabelas `aprovacoes`, `approval_certificates`, `coordenador_aprovacoes` | PRESENTE · FUNCIONA (teste) | presa ao `render_sha` |
| Navegação | `frontend/src/navigation/rotas.ts` | PRESENTE · FUNCIONA (teste, 16 ok) | 5 áreas (Início, Agentes, Estúdio de Edição, Estúdio IA, Publicações); hashes antigos continuam válidos. Área **Inteligência AUSENTE** |
| Métricas das redes | `agente.medir_post`, `aprendizado.capturar` | PRESENTE parcial | YouTube: views/curtidas/comentários; Facebook/Instagram: curtidas/comentários (views só FB); **TikTok e Kwai: nada**. Mede **uma vez** (post com mais de 2 dias, depois `medido=True`), sem série no tempo, sem retenção/CTR |
| Aprendizado | `aprendizado.py` | PRESENTE · FUNCIONA (teste, 47 ok) | só número da rede ou importado; amostra mínima; pesos com versão e desfazer; só aplica no estilo visual |
| Memória do Coordenador | tabelas `coordenador_memorias`, `_versoes`, `_evidencias` | PRESENTE | versionada; escopo por canal/vertente não existe |
| DNA do canal (`channel_identity`) | — | **AUSENTE** | o mais próximo é `perfis.py` (perfis de estilo) |
| Skills | `servidor/skills/` + tabelas `skills_*` | PRESENTE · FUNCIONA (teste) | teste_skills_agentes falha pelo `KeyError` do A2 |
| Live | `live.py` | PRESENTE · FUNCIONA (teste, 47 ok) | nunca testada com live real |
| WhatsApp / e-mail | `whatsapp.py`, `emails.py` | PRESENTE · FUNCIONA (teste) | envio real NÃO VERIFICADO |
| Segredos no site | build `frontend/dist` | sem segredo encontrado | busca por padrões de chave Google/Anthropic/Meta/GitHub no código e no build: só falsos positivos (áudio em base64). `dist/` não vai para o Git |

## 4. Itens do checklist 08 nesta fase

| Item | Estado |
|---|---|
| Documentar SHA, branch, versão do servidor, ambiente e banco | feito; celular em `main`/`b948059` com 79 GB livres (24/11); esquema do banco real não conferido |
| Backup integral e ensaio de restauração isolado | **NÃO FEITO** (precisa do celular) |
| URLs antigas e hashes | FUNCIONA (teste `rotas.test.ts`) |
| 7 agentes, sem agente novo | conferido |
| GitHub Pages sem segredos | conferido no build local |
| Suíte sem regressões novas | baseline registrada: 7 falhas já existentes antes do PR #17 |

## 5. Lacunas que viram trabalho das próximas fases

**Fase 1 (confiabilidade):**
1. A1 troca de vídeo em erro recuperável (`agente.py:2028`) e roda com `max_tentativas=1`.
2. Regra do diretor quebrou 6 testes desde cdda997: decidir teste x código.
3. `postagem.conferencia` quebra com post sem `redes` (desde 18b7382).
4. Limite de gasto barra o A3 no teste (`R$ 2,00`); começou no mesmo commit `cdda997` (que mudou `produtor.py`).
5. Estados da arquitetura mapeados sobre a fila/esteira atuais, sem trocar os nomes já salvos.
6. teste_email interativo e teste_trecho_link dependente de `yt_dlp`: marcar como manuais ou pular com aviso.

**Fase 2 em diante:** campo `track`; log de efeito aplicado no A5; rejeitar capa no A6; coleta recorrente de métricas e TikTok; área Inteligência; DNA por canal.

## 6. O que só você pode confirmar no celular

Rode no Termux e mande a saída:

```
cd ~/ia && git branch --show-current && git log -1 --oneline
python -c "import sqlite3,os;c=sqlite3.connect(os.path.expanduser('~/.estudioclip/database/studio.sqlite'));print('esquema',c.execute('PRAGMA user_version').fetchone()[0])"
df -h ~ | tail -1
```

Com isso fecho os itens "versão real do servidor", "banco real" e "branch do celular". O backup com ensaio de restauração é feito pela tela de backups (Testar restauração) e precisa ser você.
