# EstúdioClip — Radar de Canais e Editor de Cortes

Projeto inicial baseado nas especificações **V8 unificadas**, com Radar genérico (qualquer nicho), ranking de cortes, legendas e catálogo de efeitos. **Não é um produto pronto para produção**: alguns recursos são demonstrativos ou exigem configuração de serviços.

## Funciona sem servidor (GitHub Pages)

O site publicado em https://raniere3000-tech.github.io/ia/ funciona sozinho, direto no navegador. Abra a aba **Como funciona** para o passo a passo e **Chaves e ajustes** para colar as chaves (cada campo tem um botão de ajuda “Onde consigo?”).

| Função | Precisa de | Como funciona |
| --- | --- | --- |
| Radar (vídeos e canais, pesquisas salvas) | Chave grátis da YouTube Data API v3 | Consulta direta ao YouTube com a chave salva só no navegador |
| Gerar cortes | Nada | Áudio analisado no navegador; candidatos sem sobreposição, nota 0–99 e 0–10 |
| Legendas automáticas | Nada | Whisper (transformers.js) roda no navegador; o modelo é baixado na 1ª vez. Também aceita .srt/.vtt |
| Notas com IA, títulos e “refazer com pedido” | Chave da API da Claude (opcional, paga por uso) | Gancho, fluxo, valor e tendência avaliados pela Claude; no modo Gameplay envia 2 quadros por trecho |
| Editor | Nada | Ajuste de início/fim, correção da legenda, 10 estilos, 6 efeitos, 9:16 / 1:1 / 16:9, texto de gancho, duplicar versão |
| Template da marca | Nada | Logo, cor, moldura e crédito em todos os cortes |
| Exportar | Chrome, Edge ou Safari | MP4 (ou WEBM) 1080p gravado em tempo real; vários cortes em ZIP com .srt e planilha |

Cortes direto pelo link do YouTube: rode o servidor da pasta `servidor/` no seu computador (dois cliques em `iniciar-windows.bat`) e cole `http://localhost:8787` em Chaves e ajustes. Veja `servidor/README.md`.

Ainda não disponível no site: agendar/postar automaticamente nas redes (exige servidor e apps aprovados). A API Python em `backend/` continua disponível para uso local.

## Rodar interface

```bash
cd frontend
npm install
npm run dev
```

Abrir http://localhost:5173/ia/. O frontend é React/Vite, publicável via GitHub Pages. O workflow está em `.github/workflows/pages.yml`.

## Rodar API de vídeos

Requisitos: Python 3.11+, FFmpeg (ffprobe e filtro `subtitles/libass`) e memória/CPU suficientes.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --port 8000
```

Configure `YOUTUBE_API_KEY` no `.env` do backend para permitir o Radar do YouTube. Se for usar o site hospedado, o backend precisa estar hospedado separadamente em HTTPS e ter `CORS_ORIGINS` ajustado. Digite o URL dele na página Configurações do site. **Chaves de serviços não podem ficar no frontend.**

## O que a versão inicial permite

- Radar de YouTube com nichos genéricos, filtros de visualização, duração, período e ordenação por velocidade estimada.
- Inserir link de referência de canal/vídeo e abrir a origem. Download automático de terceiros **não é implementado**.
- Enviar vídeo próprio/autorizado e escolher quantidade e faixa de duração dos cortes.
- Estimar nota interna de 0–99 por energia de áudio, exibir equivalência 0–10 e filtrar acima de 3 por padrão. **Não é uma nota de viralidade confiável nem equivalente à do OpusClip.**
- Transcrição automática inicial com `faster-whisper`, quando o ambiente permitir baixar o modelo.
- Catálogo de 10 legendas e 6 efeitos carregado do JSON original; cinco legendas clássicas e fundo desfocado têm suporte inicial de renderização em MP4.
- Exportar cortes individuais em MP4 1080x1920. Os demais presets aparecem como *em desenvolvimento*.

## Limites e pendências importantes

- API sem autenticação, análise assíncrona em memória, armazenamento local, renderização síncrona. **Não publique o backend abertamente sem autenticação, rate limit e filas persistentes.**
- Ainda não implementados: IA audiovisual avançada, classificação semântica, montagem inteligente, todos os efeitos, ajustes de duração após análise, editor de linha do tempo, duplicação de projetos, exportação ZIP, Postiz e publicação automatizada.
- Para monetizar ou repostar, só materiais próprios ou com autorização adequada. Crédito não substitui autorização.
- O GitHub Pages hospeda somente a interface, não roda Python, FFmpeg nem IA.

## Arquivos principais

- `docs/estrutura-v8.md`: especificação completa original consolidada.
- `config/presets.json`: presets V8, 10 legendas + 6 efeitos.
- `frontend/src/App.tsx`: interface.
- `backend/app.py`: API e motor inicial.
- `.github/workflows/pages.yml`: implantação estática no GitHub.

## Próximos passos de engenharia

1. Revisar testes ponta-a-ponta com vídeos de amostra, garantindo legendas alinhadas ao corte e áudio correto.
2. Migrar armazenamento e filas para persistência; introduzir autenticação e quotas.
3. Adicionar a avaliação semântica (gancho, fluxo, valor, tendência) e transparência de pontuação.
4. Implementar efeitos avançados e templates, edição não destrutiva e duplicação.
5. Integrar publicação via APIs oficiais com autorização e testes reais.
