# CHECKPOINT — Download de vídeos em lote (Publicações)

Checkpoint próprio desta frente. **Não substitui** o `ESTADO_ATUAL.md` (EstúdioClip 2.0) nem o `ESTADO_ATUAL_AGENTE6.md`.

```yaml
frente: DOWNLOAD_EM_LOTE
branch: claude/project-thread-hqyqog
sha_origem: 1e89d59 (origin/main depois do PR #20)
microetapa_atual: DL.01
status: CONCLUIDA
proxima_microetapa: DL.02
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

## Como retomar

```bash
git fetch origin claude/project-thread-hqyqog && git checkout claude/project-thread-hqyqog
cat ESTADO_ATUAL_DOWNLOAD_LOTE.md
```
