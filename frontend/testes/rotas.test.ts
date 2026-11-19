// Testes do roteador das 5 áreas. Rodar: cd frontend && npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AREAS, SECOES, INICIOS, lerRota, enderecoDe, legadoParaCanonico, menuDa, secaoAtiva, areaPreferida, ABAS, type Aba } from '../src/navigation/rotas.ts';

test('exatamente cinco áreas, na ordem aprovada', ()=>{
  assert.deepEqual(AREAS.map(a=>a.nome), ['Início','Agentes','Estúdio de Edição','Estúdio IA','Publicações']);
  assert.deepEqual(AREAS.map(a=>a.curto), ['Início','Agentes','Edição','IA','Posts']);
});

test('Modelo B: Agentes abre o painel dos sete agentes, não o chat', ()=>{
  assert.equal(INICIOS.agentes, 'agentes/visao-geral');
  const r=lerRota('#agentes');
  assert.equal(r.aba, 'agentes'); assert.equal(r.area, 'agentes'); assert.equal(r.secao.secao, 'visao-geral');
  assert.equal(menuDa('agentes')[0].secao, 'visao-geral');
});

test('Coordenador fica dentro de Agentes e aceita os extras antigos', ()=>{
  const r=lerRota('#coordenador/ordens:abc123');
  assert.deepEqual([r.area,r.aba,r.extra], ['agentes','coordenador','ordens:abc123']);
  assert.equal(enderecoDe('coordenador','ordens:abc123','automacao'), '#agentes/coordenador/ordens%3Aabc123');
  const n=lerRota('#agentes/coordenador/ordens%3Aabc123');
  assert.deepEqual([n.area,n.aba,n.extra], ['agentes','coordenador','ordens:abc123']);
  assert.equal(lerRota('#agentes/memoria').extra, 'memoria');
  assert.equal(secaoAtiva('agentes','coordenador','memoria')?.secao, 'memoria');
  assert.equal(secaoAtiva('agentes','coordenador','conversar')?.secao, 'coordenador');
});

// mapa da seção 3 da especificação: endereço antigo → área e aba
const MAPA:[string,string,Aba,string][] = [
  ['#inicio','inicio','inicio',''],
  ['#coordenador','agentes','coordenador',''],
  ['#central/linhas','agentes','central','linhas'],
  ['#agente/esteira','agentes','agente','esteira'],
  ['#thumbnails/galeria:j1','agentes','thumbnails','galeria:j1'],
  ['#fila','agentes','fila',''],
  ['#revisar/p123','agentes','revisar','p123'],
  ['#manual','edicao','manual',''],
  ['#radar','edicao','radar',''],
  ['#cortes','edicao','cortes',''],
  ['#templates','edicao','templates',''],
  ['#estilos','edicao','estilos',''],
  ['#live','edicao','live',''],
  ['#vozes','estudio-ia','vozes',''],
  ['#video','estudio-ia','video',''],
  ['#ia/proj9','estudio-ia','ia','proj9'],
  ['#automatico','estudio-ia','automatico',''],
  ['#series/s1','estudio-ia','series','s1'],
  ['#galeria','estudio-ia','galeria',''],
  ['#projetos','estudio-ia','projetos',''],
  ['#agendar','publicacoes','agendar',''],
  ['#config','inicio','config',''],
];
test('todos os endereços antigos abrem a tela certa na área nova', ()=>{
  for(const [h,area,aba,extra] of MAPA){
    const r=lerRota(h);
    assert.deepEqual([r.area,r.aba,r.extra],[area,aba,extra],h);
  }
});

test('ida e volta: endereço novo → leitura → mesmo endereço', ()=>{
  for(const [h] of MAPA){
    const novo=legadoParaCanonico(h);
    const r=lerRota(novo);
    assert.equal(enderecoDe(r.aba,r.extra,r.area), novo, h+' → '+novo);
    const antigo=lerRota(h);
    assert.deepEqual([r.area,r.aba,r.extra],[antigo.area,antigo.aba,antigo.extra],h);
  }
  for(const s of SECOES){
    if(s.irPara||s.aba==='inicio'||s.aba==='config') continue;
    const e=enderecoDe(s.aba,s.extra||'',s.area);
    const r=lerRota(e);
    assert.equal(r.area,s.area,e); assert.equal(r.aba,s.aba,e); assert.equal(r.extra,s.extra||'',e);
  }
});

test('cada tela antiga tem um lugar e nenhuma sexta área aparece', ()=>{
  const antigas:Aba[]=['inicio','radar','cortes','video','vozes','manual','agendar','agente','estilos','templates','config','ia','automatico','projetos','galeria','fila','revisar','series','central','live','thumbnails','coordenador'];
  for(const a of antigas) assert.ok(ABAS.includes(a),a);
  assert.ok(SECOES.every(s=>AREAS.some(x=>x.id===s.area)));
});

test('telas em duas áreas ficam na área onde a pessoa está', ()=>{
  assert.equal(enderecoDe('vozes','','edicao'), '#edicao/vozes');
  assert.equal(enderecoDe('vozes','','estudio-ia'), '#estudio-ia/vozes');
  assert.equal(enderecoDe('vozes'), '#estudio-ia/vozes');
  assert.equal(enderecoDe('projetos','','edicao'), '#edicao/projetos');
  assert.equal(lerRota('#edicao/vozes').area, 'edicao');
  assert.equal(enderecoDe('agente','programacao','publicacoes'), '#publicacoes/programacao');
  assert.equal(enderecoDe('agente','programacao','agentes'), '#agentes/configurar/programacao');
  assert.equal(enderecoDe('agente','postagem','publicacoes'), '#agentes/configurar/postagem');
  assert.equal(enderecoDe('central','calendario','agentes'), '#agentes/automacao/calendario');
});

test('nomes de área antigos do código (automacao, fila, posts, criar) continuam funcionando', ()=>{
  assert.equal(areaPreferida('automacao','inicio'),'agentes');
  assert.equal(areaPreferida('posts','inicio'),'publicacoes');
  assert.equal(areaPreferida('criar','edicao'),'edicao');
  assert.equal(areaPreferida(undefined,'publicacoes'),'publicacoes');
  assert.equal(enderecoDe('revisar','p1',areaPreferida('fila','inicio')), '#agentes/aprovacoes/p1');
  assert.equal(enderecoDe('agendar','',areaPreferida('posts','inicio')), '#publicacoes/calendario');
});

test('atalho "Ajustes do Agente 2" em Publicações abre a configuração em Agentes', ()=>{
  const r=lerRota('#publicacoes/agente2');
  assert.deepEqual([r.area,r.aba,r.extra],['agentes','agente','postagem']);
});

test('endereços estranhos não quebram', ()=>{
  assert.equal(lerRota('').aba,'inicio');
  assert.equal(lerRota('#nada/aqui').aba,'inicio');
  assert.equal(lerRota('#agentes/nao-existe').aba,'agentes');
  assert.equal(lerRota('#%E0%A4%A').aba,'inicio');
  assert.equal(lerRota('#edicao').aba,'edicao');
  assert.equal(lerRota('#estudio-ia').aba,'estudioIA');
  assert.equal(lerRota('#publicacoes').aba,'agendar');
  assert.equal(lerRota('#thumbnails/galeria:a/b').extra,'galeria:a/b');
  assert.equal(enderecoDe('thumbnails','galeria:a/b'),'#agentes/agente/6/galeria%3Aa%2Fb');
  assert.equal(lerRota(enderecoDe('thumbnails','galeria:a/b')).extra,'galeria:a/b');
});

test('nada de senha ou sessão no endereço', ()=>{
  for(const s of SECOES) assert.ok(!/senha|token|sessao/i.test(enderecoDe(s.aba,s.extra||'',s.area)));
});
