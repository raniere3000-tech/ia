// Ponte do WhatsApp Web do EstúdioClip (roda no Termux, ao lado do servidor).
//
// Você conversa com VOCÊ MESMO no WhatsApp ("Conversar comigo" / o seu próprio contato): cada mensagem sua vira um
// comando para o servidor, e a resposta volta na mesma conversa. Os avisos do servidor (vídeo pronto, corte pronto,
// falhas) também chegam nessa conversa. Mensagens de outras pessoas e de grupos são ignoradas.
//
//   node ponte.mjs --parear 5511912345678   -> mostra o código para ligar (WhatsApp > Aparelhos conectados > Conectar com número)
//   node ponte.mjs                          -> roda (o iniciar-termux.sh liga sozinho depois de pareado)
//
// Variáveis: TOKEN (senha do servidor), PORTA (8787), PORTA_PONTE (8788), DADOS (~/.estudioclip).
// Não é a API oficial do WhatsApp: use com poucas mensagens por dia (o uso é só seu, com você mesmo).
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import pino from 'pino';
import makeWASocket, { useMultiFileAuthState, DisconnectReason, jidNormalizedUser, Browsers, fetchLatestWaWebVersion } from '@whiskeysockets/baileys';

const DADOS = process.env.DADOS || path.join(os.homedir(), '.estudioclip');
const AUTH = path.join(DADOS, 'whatsapp-sessao');
const SERVIDOR = `http://127.0.0.1:${process.env.PORTA || 8787}`;
const PORTA_PONTE = +(process.env.PORTA_PONTE || 8788);
const TOKEN = process.env.TOKEN || '';
const ROBO = '🤖 ';                      // as respostas da ponte começam assim (e por isso não viram comando de novo)
const args = process.argv.slice(2);
const parear = args[0] === '--parear' ? String(args[1] || '').replace(/\D/g, '') : '';
const log = pino({ level: process.env.LOG_PONTE || 'silent' });

let sock = null;
let eu = new Set();                      // os seus identificadores (número e LID): só eles mandam comandos
let minhaConversa = '';                  // para onde vão as respostas e os avisos
const enviadas = new Set();              // ids das mensagens que a ponte mandou (não processa de novo)
let pronta = false;

function dizer(...t) { console.log('  [WhatsApp]', ...t); }

async function chamarServidor(texto) {
  const r = await fetch(`${SERVIDOR}/agente/whatsapp/comando`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': TOKEN },
    body: JSON.stringify({ texto }), signal: AbortSignal.timeout(120000),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) return j.detail || `O servidor respondeu com erro ${r.status}.`;
  return j.resposta || '';
}

async function mandar(texto) {
  if (!sock || !pronta || !minhaConversa) throw new Error('WhatsApp ainda não está conectado.');
  const m = await sock.sendMessage(minhaConversa, { text: ROBO + String(texto).slice(0, 3500) });
  if (m?.key?.id) { enviadas.add(m.key.id); if (enviadas.size > 500) enviadas.delete(enviadas.values().next().value); }
}

function texto(msg) {
  const m = msg.message || {};
  return (m.conversation || m.extendedTextMessage?.text || m.ephemeralMessage?.message?.extendedTextMessage?.text || '').trim();
}

function deMim(msg) {
  const k = msg.key || {};
  if (!k.fromMe) return false;                                    // só mensagens que VOCÊ escreveu
  const chat = jidNormalizedUser(k.remoteJid || '');
  return eu.has(chat);                                            // ...na conversa com você mesmo
}

async function ligar() {
  fs.mkdirSync(AUTH, { recursive: true, mode: 0o700 });
  const { state, saveCreds } = await useMultiFileAuthState(AUTH);
  let version;
  try { version = (await fetchLatestWaWebVersion({})).version; } catch { /* usa a versão embutida */ }
  sock = makeWASocket({ auth: state, logger: log, browser: Browsers.ubuntu('EstúdioClip'), markOnlineOnConnect: false,
                        syncFullHistory: false, ...(version ? { version } : {}) });
  sock.ev.on('creds.update', saveCreds);

  if (parear && !state.creds.registered) {
    setTimeout(async () => {
      try {
        const cod = await sock.requestPairingCode(parear);
        console.log('\n  ============================================================');
        console.log(`  CÓDIGO PARA LIGAR O WHATSAPP:  ${cod.slice(0, 4)}-${cod.slice(4)}`);
        console.log('  No WhatsApp: Configurações > Aparelhos conectados > Conectar um aparelho');
        console.log('  > "Conectar com número de telefone" e digite o código acima.');
        console.log('  ============================================================\n');
      } catch (e) { dizer('Não consegui pedir o código:', e.message); process.exit(1); }
    }, 3000);
  }

  sock.ev.on('connection.update', async (u) => {
    if (u.connection === 'open') {
      const id = sock.user?.id || '';
      const lid = sock.user?.lid || '';
      eu = new Set([jidNormalizedUser(id), lid && jidNormalizedUser(lid)].filter(Boolean));
      minhaConversa = jidNormalizedUser(id);
      pronta = true;
      fs.writeFileSync(path.join(DADOS, 'whatsapp-ligado'), String(Date.now()));
      dizer('conectado. Mande "ajuda" na conversa com você mesmo.');
      if (parear) {
        try { await mandar('WhatsApp ligado ao EstúdioClip! Mande *ajuda* aqui nesta conversa para ver os comandos.'); } catch { /* sem problema */ }
        setTimeout(() => process.exit(0), 3000);
      }
    }
    if (u.connection === 'close') {
      pronta = false;
      const cod = u.lastDisconnect?.error?.output?.statusCode;
      if (cod === DisconnectReason.loggedOut) {
        dizer('o aparelho foi desconectado no WhatsApp. Para ligar de novo: bash iniciar-termux.sh whatsapp SEU_NUMERO');
        fs.rmSync(AUTH, { recursive: true, force: true });
        fs.rmSync(path.join(DADOS, 'whatsapp-ligado'), { force: true });
        process.exit(2);
      }
      setTimeout(ligar, 5000);                                    // caiu a conexão: tenta de novo
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' && type !== 'append') return;
    for (const msg of messages) {
      if (Date.now() / 1000 - Number(msg.messageTimestamp || 0) > 180) continue;   // não reprocessa mensagens antigas
      if (!msg.key?.id || enviadas.has(msg.key.id) || !deMim(msg)) continue;
      const t = texto(msg);
      if (!t || t.startsWith(ROBO.trim())) continue;
      try { await mandar(await chamarServidor(t)); }
      catch (e) { try { await mandar('Não consegui falar com o servidor: ' + e.message); } catch { /* desconectado */ } }
    }
  });
}

// Avisos do servidor -> sua conversa. Só aceita chamadas deste próprio celular e com a senha do servidor.
if (!parear) {
  http.createServer((req, res) => {
    const fim = (st, j) => { res.writeHead(st, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(j)); };
    if (req.method === 'GET' && req.url === '/estado') return fim(200, { pronta });
    if (req.method !== 'POST' || req.url !== '/enviar') return fim(404, { erro: 'rota' });
    if (TOKEN && req.headers['x-token'] !== TOKEN) return fim(401, { erro: 'senha' });
    let corpo = '';
    req.on('data', (c) => { corpo += c; if (corpo.length > 20000) req.destroy(); });
    req.on('end', async () => {
      try { await mandar(JSON.parse(corpo || '{}').texto || ''); fim(200, { ok: true }); }
      catch (e) { fim(503, { erro: e.message }); }
    });
  }).listen(PORTA_PONTE, '127.0.0.1');
}

ligar().catch((e) => { dizer('erro ao ligar:', e.message); process.exit(1); });
