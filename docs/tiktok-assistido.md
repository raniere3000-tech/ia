# TikTok assistido (Agente 2)

Para cada post o servidor guarda título, descrição, hashtags e links do TikTok (`tiktok_meta`). O site mostra, em **Posts**, o status e o botão **Informações do TikTok** em todos os vídeos.

**Status** (calculados, `servidor/tiktok_assistido.py`): Pendente de envio, Agendado, Enviado ao TikTok, Aguardando publicação manual, Aguardando confirmação, Publicado, Falha, Cancelado. O filtro "Status do TikTok" fica em Posts.

**Ações:** ver, editar (título, descrição, hashtags, links), copiar tudo, copiar e abrir o TikTok (fica "aguardando confirmação") e "Já publiquei" (vira publicado e guarda o link). Nenhuma dessas ações envia o vídeo de novo.

**Atualização retroativa:** roda sozinha na primeira listagem de posts depois de atualizar, ou por `POST /posts/tiktok/migrar` (`{"simular": true}` só conta). Só preenche o que falta, não troca o que existe ou foi editado, não renderiza, não cria capa, não envia ao TikTok e não apaga nada. Faz uma cópia `posts.antes-tiktok.json` antes de gravar. Textos faltantes são montados do título (sem IA, sem custo).

**Vídeo novo:** as informações são preparadas ao criar o post. Quando o vídeo chega ao TikTok, um aviso (sino, e-mail e WhatsApp, tipo `a2_tiktok`) diz que está pronto para publicar.

**Direct Post:** `modo_envio()` mantém tudo assistido até o TikTok aprovar o app. Depois, `ligar_direct_post(True)` (ou `TIKTOK_DIRECT_POST_APROVADO=1`) faz quem pediu "direto" postar direto.

Teste: `python servidor/testes/teste_tiktok_assistido.py`.
