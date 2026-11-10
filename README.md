# EstúdioClip — Radar de Canais e Editor de Cortes

Projeto inicial baseado nas especificações **V8 unificadas**, com Radar genérico (qualquer nicho), ranking de cortes, legendas e catálogo de efeitos. **Não é um produto pronto para produção**: alguns recursos são demonstrativos ou exigem configuração de serviços.

## Funciona sem servidor (GitHub Pages)

O site publicado em https://raniere3000-tech.github.io/ia/ funciona sozinho, direto no navegador:

- **Radar**: cole sua chave da YouTube Data API v3 em *Configurações*. Ela fica salva só no seu navegador e as consultas vão direto ao YouTube. Restrinja a chave ao domínio do site no Google Cloud.
- **Gerar cortes**: o vídeo é analisado no próprio navegador (energia do áudio) e não é enviado a nenhum servidor.
- **Prévia real 9:16** com os 10 estilos de legenda e os 6 efeitos.
- **Legendas**: envie um arquivo `.srt` ou `.vtt` (a transcrição automática com Whisper só existe no servidor Python).
- **Exportar**: gera o corte 1080x1920 em MP4 (Chrome, Edge, Safari) ou WEBM, gravado em tempo real. Mantenha a aba aberta durante a exportação.

Se a API Python estiver configurada em *Configurações*, o site passa a usá-la no lugar do motor do navegador.

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
