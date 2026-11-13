// Deixa o EstúdioClip instalável e abrindo rápido (e sem internet, para as telas já visitadas).
// A página principal sempre vem da rede primeiro, então as atualizações do site chegam na hora.
const CACHE = 'estudioclip-v1';
const BASE = new URL('./', self.location).pathname;   // /ia/

self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then(c => c.add(BASE)).catch(() => {})); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || req.headers.has('range')) return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(BASE)) return;   // APIs, YouTube, fontes: direto na rede
  const guardar = res => { if (res && res.ok && res.type === 'basic') { const copia = res.clone(); caches.open(CACHE).then(c => c.put(req, copia)).catch(() => {}); } return res; };
  if (req.mode === 'navigate') {
    // Página: rede primeiro; sem internet, a última versão guardada.
    e.respondWith(fetch(req).then(res => { if (res.ok) { const copia = res.clone(); caches.open(CACHE).then(c => c.put(BASE, copia)).catch(() => {}); } return res; })
      .catch(() => caches.match(BASE).then(r => r || Response.error())));
    return;
  }
  if (url.pathname.startsWith(BASE + 'assets/')) {
    // Arquivos com nome único por versão: o guardado nunca fica velho.
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(guardar)));
    return;
  }
  // Resto (ícones, motor de rosto): mostra o guardado e atualiza por trás.
  e.respondWith(caches.match(req).then(r => { const rede = fetch(req).then(guardar).catch(() => r); return r || rede; }));
});
