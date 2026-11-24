# F2.04 — DNA mínimo dos cortes

`DNA_CORTE=0` por padrão. A flag habilita a aplicação e os controles no painel
de perfis de canal. A API existente de perfis informa essa capacidade. Sem
ativação, o Agente 1 mantém as configurações anteriores.

Não há banco ou biblioteca paralela: `perfis.json` guarda `dna_corte` e o
histórico já existente versiona/restaura o campo. Perfis anteriores sem o
campo continuam legíveis, editáveis e duplicáveis, sem migração.

Template(s) e cor continuam em `templates` e `cores`. Os únicos campos novos
são fonte, legenda, zoom (1–1,6) e ritmo. Fonte aceita Inter, a única distribuída
junto com o servidor; não se promete disponibilidade de outras famílias no
Termux. Legendas reutilizam destaque, simples, caixa e nenhuma. Ritmo regula
os blocos existentes do ASS: calmo até quatro palavras/24 letras; padrão até
três/16; dinâmico até duas/12. Pausas continuam sendo respeitadas. Não acelera
a fala, não altera timestamps da fonte nem introduz cortes automáticos novos.

O A1 aplica o perfil após variar o template e reaplica em uma nova tentativa.
Momento sem fala continua sem legenda, mesmo que o canal prefira legenda.
O fluxo manual de Gameplay já escolhe perfil e template: a escolha explícita
de template prevalece e recebe os ajustes do canal. As variações do corte
registram os valores aplicados e a versão do perfil continua no histórico.

Cinco testes novos cobrem compatibilidade, restauração, isolamento de canais,
flag desligada, limpeza de entradas, grupos ASS, render real pelo A1 e numa
nova tentativa, além do template escolhido manualmente no render real. O QA
é simulado apenas nos testes de encaminhamento; os arquivos de saída são
renderizados pelo FFmpeg. Os testes completos de render/QA continuam no fecho.
