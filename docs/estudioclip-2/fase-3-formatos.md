# F3.04 — Biblioteca mínima de formatos

`FORMATOS_IA=0` por padrão. Com `1`, Criar com IA mostra três pontos de
partida: curiosidade, história narrada e vídeo explicativo. Escolher preenche
somente tipo, estilo, duração, cenas, ritmo e proporção nos campos existentes.
Tema, voz, modo de aprovação, elenco, destinos e conteúdo das cenas são mantidos.
O usuário ajusta esses campos e salva o formato na biblioteca existente.

Armazenamento: `criativo_assets`, tipo já existente `template_pack`, com o
marcador `dados.formato_ia` e seis campos em `dados.briefing`. Nenhuma tabela,
serviço ou editor novo. A leitura do catálogo não grava modelos: somente o
clique de salvar cria uma configuração. Conteúdo repetido não duplica; edição
usa versões/CAS e histórico existentes; arquivamento não é desfeito pelo catálogo.

As rotas de criação/edição de assets já existentes validam esses dados. O GET
novo `/api/v1/criativo/formatos` retorna três padrões e os formatos salvos
(visão limitada aos 50 template_pack mais recentes da biblioteca existente).
Não há chamada à IA, render, fila ou publicação ao escolher/salvar um formato.

Sete testes de API cobrem flag desligada, ausência de gravação automática,
tipos/estilos existentes, repetição, edição com versões/conflito, uso no
briefing com voz/portas/destinos preservados, dados extras removidos, entrada
inválida, arquivamento e modelos anteriores. Frontend: 16 testes e TypeScript/
build aprovados, com o aviso de chunk grande já conhecido.

O texto da opção de visão foi alinhado à política atual do Diretor: ela deixa
apontamentos no laudo para revisão; não promete liberar uma opinião pendente.
Na primeira execução do fecho, a verificação dos créditos por e-mail chegou
antes do fim da etapa de envio. O helper do teste agora aguarda o mesmo job
concluir; não foi alterado o envio real de e-mail. Logs das execuções ficam
preservados para distinguir a corrida do teste de uma regressão do produto.

Sem migrações, contas reais, merge ou deploy. Aceite no Termux permanece
pendente; dados de formatos não contêm credenciais nem política de postagem.
