// Passeio no site com servidor de verdade (dados de teste). Rodar: python3 testes/e2e-servidor.py & npx vite preview --port 4173 ; node testes/e2e-areas.cjs
const { chromium } = require('playwright');
const BASE='http://localhost:4173/ia/';
let ok=0, fal=0; const conf=(c,n)=>{ if(c){ok++;console.log('  ok ',n);} else {fal++;console.log('  FALHOU',n);} };
(async()=>{
  const b=await chromium.launch();
  const nova=async(vp)=>{ const ctx=await b.newContext({viewport:vp,deviceScaleFactor:1}); const p=await ctx.newPage();
    const erros=[]; p.on('pageerror',e=>erros.push(String(e))); p.on('console',m=>{ if(m.type()==='error'&&!/favicon|Failed to load resource|net::/.test(m.text())) erros.push(m.text()); });
    await p.addInitScript(()=>{ localStorage.setItem('studio_settings',JSON.stringify({servidor:'http://127.0.0.1:8799',servidorToken:'senha-e2e-123'})); localStorage.setItem('studio_tour',JSON.stringify({versao:99,resposta:'nunca'})); });
    p.erros=erros; return p; };
  const estouro=async p=>p.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);

  console.log('1. computador 1440x900');
  let p=await nova({width:1440,height:900});
  await p.goto(BASE+'#inicio'); await p.waitForSelector('.kpis .kpi b'); await p.waitForTimeout(1500);
  conf(await p.locator('nav.areas > .area-grupo').count()===5,'exatamente 5 áreas no menu');
  conf((await p.locator('nav.areas .area-btn > span').allTextContents()).join('|')==='Início|Agentes|Estúdio de Edição|Estúdio IA|Publicações','nomes das 5 áreas');
  const kpiTxt=(await p.locator('.kpis').innerText()); conf(/2\s*\n?\s*vídeos produzidos/.test(kpiTxt),'Início: vídeos produzidos hoje = 2 (do servidor)');
  conf(/Não disponível\s*\n?\s*aprovados/.test(kpiTxt),'Início: aprovados "Não disponível" com a esteira desligada (não 0)');
  conf(/História do café/.test(await p.locator('.pi-trab').innerText()),'Início: quem está trabalhando agora (Agente 3, História do café)');
  conf(/40%/.test(await p.locator('.pi-trab').innerText()),'Início: % só porque o servidor mediu progresso');
  conf(/Por que o céu é azul/.test(await p.locator('.pi-prox').innerText()),'Início: próxima publicação');
  conf(/envio\(s\) para redes com erro/.test(await p.locator('.pi-alertas').innerText()),'Início: alerta do post com erro');
  await p.screenshot({path:(process.env.FOTOS||'.')+'/d-inicio.png',fullPage:false});
  await p.click('[data-tour="area-agentes"]'); await p.waitForSelector('.agente-card');
  conf(p.url().endsWith('#agentes/visao-geral'),'tocar em Agentes abre #agentes/visao-geral (Modelo B)');
  conf(await p.locator('.agente-card').count()===7,'sete cartões de agentes');
  conf(await p.locator('.coord-msgs').count()===0,'Agentes não abre o chat');
  conf(/Agente 3[\s\S]*Trabalhando/.test(await p.locator('.agente-card').nth(2).innerText()),'cartão do Agente 3 trabalhando (dado real da fila)');
  conf(/Parado/.test(await p.locator('.agente-card').nth(6).innerText()),'Agente 7 parado (tela aberta não conta como rodando)');
  conf(await p.locator('.nav-subs .nav.sub').count()===9,'submenu de Agentes com 9 seções');
  await p.screenshot({path:(process.env.FOTOS||'.')+'/d-agentes.png'});
  await p.locator('.agente-card').nth(6).getByText('Conversar').click(); await p.waitForSelector('.coord-chat');
  conf(/#agentes\/coordenador\/conversar$/.test(p.url()),'cartão do A7 → Coordenador real (conversar)');
  await p.goBack(); await p.waitForSelector('.agente-card'); conf(p.url().endsWith('#agentes/visao-geral'),'Voltar volta ao painel dos agentes');
  await p.goForward(); await p.waitForSelector('.coord-chat'); conf(/coordenador/.test(p.url()),'Avançar volta ao Coordenador');
  await p.locator('.agente-card').count();
  await p.goto(BASE+'#agentes/visao-geral'); await p.waitForSelector('.agente-card');
  await p.locator('.agente-card').nth(5).getByText('Abrir').click(); await p.waitForTimeout(800);
  conf(/#agentes\/agente\/6\/fila$/.test(p.url()),'cartão do A6 → tela real de capas');
  // atalho global
  await p.goto(BASE+'#edicao/radar'); await p.waitForTimeout(800);
  await p.click('.coord-rapido'); await p.waitForSelector('.coord-drawer .coord-chat');
  conf(/#edicao\/radar$/.test(p.url()),'atalho do Coordenador abre por cima, sem sair do Radar');
  await p.fill('.coord-drawer textarea','rascunho de teste'); await p.keyboard.press('Escape'); await p.waitForTimeout(300);
  conf(await p.locator('.coord-drawer').count()===0,'Esc fecha o atalho'); conf(/#edicao\/radar$/.test(p.url()),'continua no Radar');
  await p.goto(BASE+'#agentes/coordenador'); await p.waitForSelector('.coord-chat textarea');
  conf(await p.inputValue('.coord-chat textarea')==='rascunho de teste','mesmo rascunho na tela do Coordenador (não é um segundo chat)');
  await p.goto(BASE+'#edicao/radar'); await p.waitForTimeout(500); await p.click('.coord-rapido'); await p.waitForSelector('.coord-drawer');
  await p.goBack(); await p.waitForTimeout(400); conf(await p.locator('.coord-drawer').count()===0&&/#edicao\/radar$/.test(p.url()),'Voltar fecha o atalho e fica no Radar');

  console.log('2. endereços antigos');
  const LEG=[['#coordenador/ordens:abc','#agentes/coordenador/ordens%3Aabc','.coord'],['#central/linhas','#agentes/automacao/linhas',null],['#thumbnails/galeria','#agentes/agente/6/galeria',null],
    ['#fila','#agentes/execucoes',null],['#revisar','#agentes/aprovacoes','.aprovacoes'],['#manual','#edicao/manual',null],['#radar','#edicao/radar',null],['#cortes','#edicao/cortes',null],
    ['#templates','#edicao/templates',null],['#estilos','#edicao/legendas-efeitos',null],['#live','#edicao/live',null],['#vozes','#estudio-ia/vozes',null],['#video','#estudio-ia/animado',null],
    ['#ia','#estudio-ia/criar',null],['#automatico','#estudio-ia/lote',null],['#series','#estudio-ia/series',null],['#galeria','#estudio-ia/biblioteca',null],['#projetos','#estudio-ia/projetos',null],
    ['#agendar','#publicacoes/calendario',null],['#agente/postagem','#agentes/configurar/postagem',null],['#config','#config',null]];
  for(const [a,n,sel] of LEG){ await p.goto(BASE+a); await p.waitForTimeout(700); const u=decodeURIComponent(new URL(p.url()).hash);
    conf(u===decodeURIComponent(n)&&!(await p.locator('.erro-tela, .tela-erro').count()),`${a} → ${n}`); if(sel) conf(await p.locator(sel).count()>0,`  ${a} mostra a tela certa`); }
  await p.goto(BASE+'#agentes/aprovacoes'); await p.waitForTimeout(800);
  conf(/Pacotes do Coordenador/.test(await p.locator('main').innerText()),'Aprovações lista o que espera decisão');
  await p.reload(); await p.waitForTimeout(800); conf(p.url().endsWith('#agentes/aprovacoes'),'recarregar mantém a rota');
  conf((await p.locator('.chip-aba.active').innerText()).includes('Aprovações'),'subnav marca Aprovações a partir do deep link');
  // VIVAS: troca de área não desmonta a montagem manual
  await p.goto(BASE+'#edicao/manual'); await p.waitForTimeout(1500);
  await p.evaluate(()=>{ const el=document.querySelector('[data-tela="manual"]'); el&&(el.dataset.marca='viva'); });
  await p.click('[data-tour="area-agentes"]'); await p.waitForTimeout(600); await p.click('[data-tour="area-publicacoes"]'); await p.waitForTimeout(600);
  await p.click('[data-tour="area-edicao"]'); await p.waitForTimeout(500); await p.click('.chip-aba:has-text("Montagem manual")'); await p.waitForTimeout(500);
  conf(await p.evaluate(()=>document.querySelector('[data-tela="manual"]')?.getAttribute('data-marca'))==='viva','Montagem manual continua viva ao trocar Edição → Agentes → Publicações → Edição');
  // Publicações
  await p.click('[data-tour="area-publicacoes"]'); await p.waitForTimeout(800);
  conf(p.url().endsWith('#publicacoes/calendario'),'Publicações abre no calendário/posts');
  await p.click('.chip-aba:has-text("Ajustes do Agente 2")'); await p.waitForTimeout(800);
  conf(p.url().endsWith('#agentes/configurar/postagem'),'atalho Ajustes do Agente 2 → configuração em Agentes (sem duplicar)');
  await p.click('[data-tour="ajustes"]'); await p.waitForTimeout(500); conf(p.url().endsWith('#config')&&await p.locator('nav.areas > .area-grupo').count()===5,'Ajustes pela engrenagem, sem sexta área');
  await p.goto(BASE+'#edicao'); await p.waitForSelector('.hub-acao'); conf((await p.locator('.hub-acao').allTextContents()).join('|').includes('Novo projeto'),'Estúdio de Edição: Novo projeto, Continuar, Abrir editor, Radar e Cortes');
  await p.screenshot({path:(process.env.FOTOS||'.')+'/d-edicao.png'});
  await p.goto(BASE+'#estudio-ia'); await p.waitForSelector('.hub-acao'); const ia=(await p.locator('.hub-acoes').innerText());
  conf(['Criar com IA','Séries e personagens','Produção em lote','Biblioteca criativa'].every(x=>ia.includes(x)),'Estúdio IA: as 4 ações');
  await p.screenshot({path:(process.env.FOTOS||'.')+'/d-estudio-ia.png'});
  await p.goto(BASE+'#estudio-ia/projetos'); await p.waitForTimeout(800); conf(await p.locator('[role=radio][aria-checked=true]:has-text("Estúdio IA")').count()===1,'Projetos abre filtrado pelo estúdio de origem');
  conf(p.erros.length===0,'sem erro no console: '+p.erros.slice(0,3).join(' | '));
  await p.context().close();

  console.log('3. tamanhos de tela');
  for(const vp of [{width:360,height:800},{width:390,height:844},{width:768,height:1024},{width:1024,height:768},{width:1440,height:900}]){
    const q=await nova(vp); const nome=vp.width+'x'+vp.height;
    for(const r of ['#inicio','#agentes/visao-geral','#edicao','#estudio-ia','#publicacoes/calendario','#agentes/coordenador']){
      await q.goto(BASE+r); await q.waitForTimeout(r==='#inicio'?1800:1000);
      const e=await estouro(q); conf(e<=0,`${nome} ${r}: sem rolagem lateral (${e}px)`);
    }
    const vis=await q.locator('nav.areas > .area-grupo').evaluateAll(l=>l.filter(x=>x.getBoundingClientRect().width>0).length); conf(vis===5,`${nome}: 5 destinos visíveis`);
    if(vp.width<=820){ const alt=await q.locator('nav.areas .area-btn').evaluateAll(l=>Math.min(...l.map(x=>x.getBoundingClientRect().height))); conf(alt>=44,`${nome}: botões da barra com ${Math.round(alt)}px de altura (mín. 44)`); }
    await q.goto(BASE+'#agentes/visao-geral'); await q.waitForSelector('.agente-card'); await q.waitForTimeout(800); await q.screenshot({path:`agentes-${nome}.png`,fullPage:false});
    await q.goto(BASE+'#inicio'); await q.waitForSelector('.kpis .kpi b'); await q.waitForTimeout(1200); await q.screenshot({path:`inicio-${nome}.png`,fullPage:false});
    if(vp.width<=820){ await q.click('.topo-movel [aria-label="Falar com o Coordenador"]'); await q.waitForSelector('.coord-drawer textarea'); await q.waitForTimeout(500); await q.screenshot({path:`coord-${nome}.png`}); }
    await q.context().close();
  }
  console.log(`\n${ok} ok, ${fal} falharam`); await b.close(); process.exit(fal?1:0);
})().catch(e=>{ console.error(e); process.exit(2); });
