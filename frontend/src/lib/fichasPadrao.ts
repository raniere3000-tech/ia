// Fichas prontas que já vêm no site e o modelo em branco de como escrever uma ficha.

export const GUIA_FICHA = `Personagem\tVoz-base\tGravidade\tRitmo\tEnergia\tEmoção de base\tIntensidade
Nome\tCharon\t70%\t45%\t50%\tNeutra\t50%

Nome · Função (opcional)
Perfil — Quem é: gênero, idade, jeito (ex.: homem maduro, narrador teatral de humor seco).

Descrição e direção permanente
Como a voz soa e como deve interpretar em todas as falas: timbre, dicção, pausas, o que muda em cada momento.

Teste — “Uma frase curta que o personagem diria.”
Teste — “Outra frase, de preferência com outro clima.”`;

export const FICHAS_PRONTAS:{id:string;nome:string;texto:string}[] = [{id:'destino-ep1',nome:'Destino em Jogo — episódio 1',texto:`Fichas de voz — Destino em Jogo, episódio 1
Use Pro (mais expressivo) e brasileiro neutro nas oito fichas.
Personagem\tVoz-base\tGravidade\tRitmo\tEnergia\tEmoção de base
Narrador\tCharon\t72%\t42%\t45%\tNeutra
Thorgar\tAlgenib\t90%\t58%\t85%\tEntusiasmada
Vaelic\tUmbriel\t65%\t34%\t25%\tCansada
Aldric\tOrus\t60%\t48%\t62%\tFirme
Kael\tPuck\t37%\t72%\t56%\tBrincalhona
Garçonete\tLeda\t32%\t67%\t58%\tAssustada
Cliente\tZubenelgenubi\t55%\t63%\t72%\tIndignada
Capitão\tAlnilam\t77%\t45%\t78%\tAutoritária

Narrador
Perfil — Homem maduro, contador de histórias de fantasia, teatral e de humor seco.

Descrição e direção permanente
Voz encorpada, dicção clara e pausas intencionais. Na taverna, conte o caos com a calma de quem já sabe como tudo vai terminar. Faça uma pequena pausa antes das viradas cômicas. Depois da explosão na cela, mantenha o mesmo timbre, desacelere e deixe a ameaça aparecer na voz. No encerramento, fale diretamente com quem assiste e sustente a pausa antes de “é você”.

Teste na taverna — “Era uma noite tranquila na taverna. Infelizmente... Thorgar também estava lá.”

Teste no encerramento — “O destino está em jogo. E quem decide... é você.”
Thorgar · Bárbaro
Perfil — Homem adulto, expansivo, impulsivo e genuinamente animado com uma briga.

Descrição e direção permanente
Voz muito grave, rouca e ressonante, com projeção de peito. A irritação explode rápido e vira alegria assim que alguém o desafia. Deixe o sorriso aparecer na voz. Quando se diverte, a gargalhada é aberta e espontânea. Nas falas altas, mantenha as palavras bem articuladas.

Teste na taverna — “DESDE QUE CHEGUEI!”

Teste na cela — “Eu estava! Foi excelente!”
Vaelic · Mago
Perfil — Homem adulto, cansado, reservado e sarcástico.

Descrição e direção permanente
Voz médio-grave, baixa e seca, com finais de frase ligeiramente descendentes. Use pausas curtas e deixe o sarcasmo sair como um comentário casual. Depois de perder a bebida, fale com resignação. Na cela, quando percebe a sombra, a voz continua baixa, mas as palavras saem mais nítidas e a pausa ganha tensão.

Teste de sarcasmo — “Eu só queria beber em paz...”

Teste de suspense — “Isso não parece normal...”
Aldric · Paladino
Perfil — Homem adulto, nobre, disciplinado e convicto do seu dever.

Descrição e direção permanente
Voz firme, clara e bem projetada, com dicção precisa e postura cerimoniosa. Na primeira intervenção, fale alto para alcançar a taverna inteira, com convicção de que ainda dá para acalmar a briga. Depois do soco, faça uma pausa, baixe o volume e diga a próxima frase com determinação. Na cela, deixe a indignação escapar pela primeira vez.

Teste antes do soco — “EM NOME DA DEUSA! CESSEM ESTA VIOLÊNCIA! Podemos resolver isso civilizadamente!”

Teste depois do soco — “Muito bem. A justiça também conhece outros métodos.”
Kael · Ladino metamorfo
Perfil — Homem jovem, ágil, esperto e convincente quando finge inocência.

Descrição e direção permanente
Voz jovem e leve, com articulação rápida e um sorriso discreto nas palavras. Ao comentar os furtos, fale baixo, como quem se diverte sozinho com a própria piada. Quando é acusado, responda de imediato, com surpresa calculada. No disfarce, mantenha a mesma voz-base e dê à fala uma polidez improvisada, com uma pequena pausa entre as duas perguntas.

Teste no rosto original — “Que tragédia... tanta gente perdendo seus pertences.”

Teste disfarçado — “Ladrão? Onde?!”
Garçonete
Perfil — Mulher jovem adulta, educada, trabalhadora e pega de surpresa pelo acidente.

Descrição e direção permanente
Voz clara, jovem e cordial. A primeira frase sai depressa, com um susto breve na respiração. A segunda é um pouco mais firme, como alguém que tenta se explicar antes que a situação piore. Preserve a naturalidade de uma pessoa falando de perto.

Teste — “Mil perdões, senhor! Foi um acidente!”
Cliente da taverna
Perfil — Homem adulto, direto, indignado e disposto a intervir.

Descrição e direção permanente
Voz coloquial e áspera na medida, com frases curtas e ataque firme nas primeiras palavras. Ao defender a garçonete, fale como quem interrompe uma injustiça e sustenta o desafio. Na denúncia do furto, projete a voz para atravessar o barulho da taverna e articule a ordem inteira.

Teste ao defender a garçonete — “Ei, grandalhão! Ela já pediu desculpas! Tá procurando briga?”

Teste ao denunciar o furto — “LADRÃO! PEGUEM AQUELE HOMEM!”
Capitão da guarda
Perfil — Homem maduro, experiente, acostumado a ser obedecido.

Descrição e direção permanente
Voz grave, firme e disciplinada. Projete a ordem com articulação incisiva. Diga “PAREM!” como um comando curto que corta a confusão. Faça uma pausa curta e dê a ordem de prisão com autoridade e volume sustentado.

Teste — “PAREM! TODOS ESTÃO PRESOS!”`}];
