const { chromium, devices } = require('playwright');
const fs=require('fs'); const SP=process.env.SP||'.'; let ok=0,fal=0; const conf=(c,n)=>{ if(c){ok++;console.log('  ok ',n);}else{fal++;console.log('  FALHOU',n);} };
(async()=>{
  const b=await chromium.launch();
  for (const [nome,ctxopts] of [['computador',{viewport:{width:1280,height:900}}],['celular',{...devices['Pixel 7']}]]) {
    console.log('== '+nome);
    const ctx=await b.newContext({...ctxopts,acceptDownloads:true}); const p=await ctx.newPage();
    const erros=[]; p.on('pageerror',e=>erros.push(String(e)));
    await p.addInitScript(()=>{ localStorage.setItem('studio_settings',JSON.stringify({servidor:'http://127.0.0.1:8798',servidorToken:'senha-e2e-123'})); localStorage.setItem('studio_tour',JSON.stringify({versao:99,resposta:'nunca'})); });
    await p.goto('http://localhost:4173/ia/#agendar'); await p.waitForSelector('.posts-lote-barra'); await p.waitForTimeout(500);
    const barra=await p.locator('.posts-lote-barra').innerText();
    conf(/Baixar selecionados \(0\)/.test(barra)&&/Agendar selecionados \(0\)/.test(barra),'botões Baixar e Agendar lado a lado, com contagem');
    conf(await p.getByRole('button',{name:/Baixar selecionados/}).isDisabled(),'Baixar desligado sem seleção');
    // 'Todas as redes' + situação 'pendentes' esconde o publicado? seleciona todos do filtro
    await p.locator('.posts-lote-barra input[type=checkbox]').check();
    const n1=await p.locator('.posts-lote-barra span').innerText(); console.log('   ',n1);
    await p.getByRole('button',{name:/Baixar selecionados/}).click(); await p.waitForSelector('.modal');
    conf(/selecionado\(s\) entre os/.test(await p.locator('.modal').innerText()),'janela explica o alcance da seleção');
    conf(await p.locator('.modal [role=radio][aria-checked=true]').innerText().then(t=>/Pacote completo/.test(t)),'pacote completo vem marcado (recomendado)');
    await p.screenshot({path:`${SP}/dl-modal-${nome}.png`});
    await p.getByRole('button',{name:/Preparar download/}).click();
    await p.waitForSelector('text=/Baixar EstudioClip_/',{timeout:60000});
    const txt=await p.locator('.modal').innerText();
    conf(/Resultado parcial/.test(txt)&&/indisponível/.test(txt)||/Pronto, completo/.test(txt),'resultado declarado ('+(/parcial/.test(txt)?'parcial':'completo')+')');
    await p.screenshot({path:`${SP}/dl-pronto-${nome}.png`,fullPage:true});
    const [d]=await Promise.all([p.waitForEvent('download'),p.getByRole('button',{name:/Baixar EstudioClip_/}).click()]);
    const dest=`${SP}/baixado-${nome}.zip`; await d.saveAs(dest);
    const sz=fs.statSync(dest).size;
    conf(/^EstudioClip_\d{4}-\d{2}-\d{2}_\d{4}\.zip$/.test(d.suggestedFilename())&&sz>1000,`download real do navegador: ${d.suggestedFilename()} (${sz} bytes)`);
    conf(erros.length===0,'sem erro no console '+JSON.stringify(erros));
    await ctx.close();
  }
  await b.close(); console.log(`\n${ok} ok, ${fal} falha(s)`); process.exit(fal?1:0);
})();
