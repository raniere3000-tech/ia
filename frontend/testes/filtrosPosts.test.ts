import { test } from 'node:test';
import assert from 'node:assert/strict';
import { filtrarPosts, horaDaRede } from '../src/lib/filtrosPosts.ts';
import type { Post } from '../src/lib/agenda.ts';
const p=(id:string,redes:Post['redes'],extra:Partial<Post>={}):Post=>({id,video:id,criado:1,quando:100,titulo:id,legenda:'',opcoes:{youtube_privacidade:'public',tiktok_modo:'rascunho'},redes,...extra});
const feito={status:'postado',link:'https://exemplo',erro:''} as const;
const agendado={status:'agendado',link:'',erro:''} as const;

test('publicado no YouTube continua pendente no TikTok, inclusive sem destino cadastrado',()=>{
 const posts=[p('a',{youtube:feito}),p('b',{youtube:feito,tiktok:agendado})];
 assert.equal(filtrarPosts(posts,'tiktok','pendentes',200).length,2);
 assert.equal(filtrarPosts(posts,'youtube','pendentes',200).length,0);
 assert.equal(filtrarPosts(posts,'youtube','publicados',200).length,2);
 assert.deepEqual(filtrarPosts(posts,'tiktok','nao_agendados',200).map(p=>p.id),['a']);
});
test('filtro e horário da rede ignoram data antiga de outra publicação',()=>{
 const posts=[p('a',{youtube:feito,tiktok:{...agendado,quando:500}})];
 assert.equal(filtrarPosts(posts,'tiktok','agendados',200).length,1);
 assert.equal(filtrarPosts(posts,'tiktok','atrasados',200).length,0);
 assert.equal(horaDaRede(posts[0],posts[0].redes.tiktok),500);
});
test('duplicatas entre posts não viram pendência falsa nem contam duas vezes por rede',()=>{
 const posts=[p('a',{youtube:feito},{hash:'video-igual'}),p('b',{tiktok:feito},{hash:'video-igual'})];
 assert.equal(filtrarPosts(posts,'tiktok','pendentes',200).length,0);
 assert.equal(filtrarPosts(posts,'tiktok','publicados',200).length,1);
});
test('rede ausente não entra em disponíveis quando arquivo sumiu ou está preparando',()=>{
 const posts=[p('a',{youtube:feito},{arquivo_disponivel:false}),p('b',{youtube:feito},{preparando:true})];
 assert.equal(filtrarPosts(posts,'tiktok','nao_agendados').length,0);
});
test('erros, pausados e cancelados mantêm filtros distintos',()=>{
 const posts=[p('a',{tiktok:{...agendado,status:'erro'}}),p('b',{tiktok:{...agendado,lote_pausado:true}}),p('c',{tiktok:{...agendado,status:'cancelado'}})];
 assert.deepEqual(filtrarPosts(posts,'tiktok','erros').map(p=>p.id),['a']);
 assert.deepEqual(filtrarPosts(posts,'tiktok','pausados').map(p=>p.id),['b']);
 assert.deepEqual(filtrarPosts(posts,'tiktok','cancelados').map(p=>p.id),['c']);
 assert.equal(filtrarPosts(posts,'tiktok','pendentes').length,2);
 assert.equal(filtrarPosts(posts,'tiktok','atrasados').length,0);
});
