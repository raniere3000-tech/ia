# CHECKPOINT — Download de vídeos em lote (Publicações)

Checkpoint próprio desta frente. **Não substitui** o `ESTADO_ATUAL.md` (EstúdioClip 2.0) nem o `ESTADO_ATUAL_AGENTE6.md`.

```yaml
frente: DOWNLOAD_EM_LOTE
branch: claude/project-thread-hqyqog
sha_origem: 1e89d59 (origin/main depois do PR #20)
microetapa_atual: DL.06
status: CONCLUIDA
proxima_microetapa: VALIDACAO_NO_ANDROID_E_REVISAO_DO_PR
merge: NAO_REALIZADO
producao: NAO_PUBLICADA
publicacoes_reais_em_teste: NENHUMA
```

## DL.01 — Auditoria (estado real, 24/11/2026)

**Tela e seleção** (`frontend/src/pages/Agendar.tsx`, aba Publicações):
- Já existe a seleção em lote: `selecionados` (Set de ids de post, até 200), checkbox por linha (`PostLinha.onSelecionar`), "Selecionar resultados do filtro (até 200)", "Limpar seleção" e o botão **Agendar selecionados** (abre `AgendarLote`). Reaproveitar tudo isso; o botão Baixar entra ao lado.
- `podeSelecionar(p)` hoje exige `arquivo_disponivel!==false`, não estar preparando e, com rede filtrada, não estar postado/postando nessa rede. Para baixar, o critério é outro (pendente, agendado e **publicado** valem; só precisa do arquivo no servidor), então a seleção para download não pode reutilizar `podeSelecionar` sem ampliar — ver plano.
- **Não há paginação**: a lista é inteira (`lista`), o teto de 200 é só da seleção. "Selecionar todos do filtro" cobre tudo que o filtro mostra; o limite será declarado na tela.
- Já existe download de 1 vídeo: botão **Baixar** → `baixarVideoPost` (`lib/agenda.ts`) faz `fetch` com a senha no cabeçalho, lê tudo em memória (`blob`) e nomeia com o título. Funciona, mas não é bom para ZIP grande no Android.

**Servidor** (Termux, Python):
- Posts: `postagem.posts()` / `lista_posts()`; cada post tem `id`, `video` (nome do arquivo em `DADOS/videos`, `video_path()` acha `.mp4/.webm/.mov`), `titulo`, `legenda`, `redes{rede:{status,link,erro}}`, `hash`, `tiktok_meta` (título, descrição, hashtags e links próprios do TikTok), `projeto`, `render_sha`.
- Metadados **distintos por rede só existem no TikTok** (`tiktok_meta`). YouTube/Instagram/Facebook/Kwai usam o mesmo `titulo` + `legenda` do post. O TXT vai refletir isso, sem inventar campos.
- Capa aprovada: `thumbnails.capa_para_video(arq)` (hash do arquivo). Ela **revoga** seleção velha ao conferir (escreve no banco). Para baixar não pode haver escrita: o download terá a própria checagem só de leitura (mesma regra: seleção ativa para o hash do vídeo + hash do arquivo da capa igual).
- Entrega de arquivo: `Handler.enviar_parcial` já suporta HTTP Range e `Content-Disposition`; `api_v1.Resposta(arquivo, mime, nome, baixar)`. Links assinados (`au.assinar_url`) funcionam só para prefixos listados em `servidor.py` (`/api/v1/assets/`, `/thumbnails/midia/`, `/kwai/`): o download por link do navegador (sem carregar em memória) pede acrescentar um prefixo novo, `/api/v1/downloads/`.
- Fila de jobs duráveis (`fila.py`) é para os agentes; o preparo do ZIP **não** passa por ela (o spec pede independência dos agentes). Terá um gerenciador próprio com 1 preparo por vez, estado em `kv` (sem migração de banco, para não colidir com a numeração da Fase 2 / Agente 6) e arquivos temporários em `DADOS/downloads/`.
- Rota atual de vídeo: `GET /posts/<id>/video` (autenticada por cabeçalho). Continua igual.

**Riscos encontrados**
1. Memória: o fluxo atual carrega o vídeo inteiro no navegador. Para vários vídeos, usar link assinado do ZIP/MP4 (o navegador/Android gerencia o arquivo).
2. Android: vários downloads simultâneos são bloqueados/descartados; MP4 individuais serão sequenciais, com botão por item.
3. `capa_para_video` escreve no banco (revoga). Não usar no download.
4. Nomes: título pode ter acentos, emoji, `/`, `..`; ids de post têm 10 caracteres hex; títulos iguais são comuns.

## Plano de mudanças

- **DL.02** `Agendar.tsx`: botão "Baixar selecionados (N)" ao lado do agendar; janela com 3 opções (padrão: Pacote completo); seleção própria que inclui publicados. Sem mudar o agendamento.
- **DL.03** `servidor/download_lote.py` (novo): nomes base seguros, TXT UTF-8 por vídeo, capa com extensão real, MP4 individual autorizado.
- **DL.04** mesmo módulo: preparo do ZIP por streaming (ZIP_STORED), progresso, cancelar, falha parcial + `RELATORIO.txt`, limpeza, espaço livre, Range.
- **DL.05** rotas em `api_v1.py`/`servidor.py`, `frontend/src/lib/download.ts`, teste no navegador (Playwright) com o servidor de teste.
- **DL.06** regressão, doc e PR.

## DL.02 — Seleção em lote e janela (concluída)

- `Agendar.tsx`: botão **Baixar selecionados (N)** ao lado de **Agendar selecionados (N)**; seleção reaproveitada (agora aceita também vídeos já publicados; o agendamento usa só os agendáveis, `idsAgendar`, com o mesmo limite de 200). "Selecionar todos do filtro (N)" cobre toda a lista filtrada (não há paginação), limite 300 por vez, texto de alcance na janela.
- `components/DownloadLote.tsx` + `lib/download.ts`: janela com 3 formatos (pacote completo recomendado), progresso, cancelar, falhas, tentar novamente, fila de MP4 um por vez. **Chama rotas `/api/v1/downloads` que nascem em DL.03/DL.04** (até lá o botão abre a janela e o servidor responde 404).
- Testes: `tsc` limpo, `npm test` 16 ok. Servidor não mudou nesta etapa.

## DL.03 + DL.04 — Servidor (concluídas; feitas juntas porque o preparo do ZIP usa os nomes e o TXT)

- `servidor/download_lote.py` (novo): `limpar_nome`/`nome_base` (`001 - Título - a1b2c3`: sem emoji, sem `/ \ : * ? " < > |`, sem `..`, até 80 caracteres de título; sem título = `Video - ID`), `texto_publicacao` (TXT UTF-8 por vídeo, um bloco por rede do post, só metadados salvos; TikTok usa `tiktok_meta`; ausente = `[não configurado]`), `capa_do_video` (somente leitura: capa aprovada para o hash EXATO do arquivo; extensão pelo conteúdo — PNG/JPEG/WEBP; nunca revoga seleção), `criar/obter/cancelar/tentar_de_novo/limpar`.
- ZIP por streaming (`ZIP_STORED`, 1 MB por vez), um preparo por vez (semáforo), checagem de espaço livre (+200 MB de folga), progresso em `kv` (`download.job.<id>`, sem migração de banco), `.part` renomeado só no fim, cancelar apaga temporários, job `preparando` sem fio vivo (servidor reiniciou) vira `falhou` com saída "tentar novamente", arquivos prontos somem em 24 h. Cópia que muda no meio aborta o job (nunca entrega MP4 pela metade como sucesso). `RELATORIO.txt` dentro do ZIP quando há ausentes, falhas ou vídeos sem capa; estado `parcial` quando algum vídeo não entrou.
- Rotas (`api_v1._downloads`): `POST /api/v1/downloads`, `GET /api/v1/downloads/<id>`, `POST .../cancelar|tentar-novamente`, `GET .../arquivo` e `.../item/<n>` (links assinados de 6 h, sem a senha na URL; Range para retomar). `servidor.py`: prefixo `/api/v1/downloads/` aceita assinatura; `Content-Disposition` agora também manda `filename*=UTF-8''...` (antes um nome fora do latin-1 quebraria o cabeçalho).
- Teste novo `servidor/testes/teste_download_lote.py`: 65 ok (nomes maliciosos, títulos iguais, TXT, estrutura do ZIP, capa PNG com nome .jpg, MP4 certo para cada vídeo, parcial, relatório, Range, assinatura adulterada, sem login, capa desatualizada, falta de espaço, cancelar, repetir, reinício, limpeza, e "posts/capas/fila/vídeos não mudaram").
- Regressão rápida: `teste_thumbnails` 101, `teste_exportacao` 23, `teste_publicacao_lotes` 12, `teste_tiktok_assistido` 41.

## DL.05 — Site + servidor no navegador (concluída)

- Teste de ponta a ponta com o servidor de verdade e Chromium: `frontend/testes/e2e-download-servidor.py` + `frontend/testes/e2e-download.cjs` (computador 1280x900 e Pixel 7 emulado). 14 ok: botões lado a lado, desligado sem seleção, janela com alcance, pacote completo marcado, preparo, **download real** do ZIP pelo navegador (633 KB, 2 vídeos), sem erro no console. ZIP aberto: pastas, MP4, TXT, `RELATORIO.txt` (sem capa), `testzip` ok.
- **Limite honesto:** isto NÃO é Android real nem Termux. Pendente de você: baixar no celular com o servidor Termux (pacote e ZIP) e, com 3 agentes rodando, medir tempo/memória. Nada foi medido nem inventado.

## DL.06 — Regressão e entrega (concluída)

- Suíte completa do servidor na branch: o conjunto de falhas é **idêntico ao baseline da Fase 0** (agente3, central_automacao, comandos, coordenador, descricao, liberacao, skills_agentes — já falhavam em main) mais os 2 de ambiente (`teste_email` pede digitação, `teste_trecho_link` sem `yt_dlp`). Nenhum teste novo quebrou; `teste_download_lote` 65 ok.
- Frontend: `tsc` limpo, `npm run build` ok, `npm test` 16 ok.
- Doc: `docs/download-em-lote.md`.
- **Pendências reais:** teste no Android com servidor Termux; medir impacto com 3 agentes rodando; nenhum envio a redes foi feito.

## Como retomar

```bash
git fetch origin claude/project-thread-hqyqog && git checkout claude/project-thread-hqyqog
cat ESTADO_ATUAL_DOWNLOAD_LOTE.md
```
