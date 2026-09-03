// 마이헬스케어 PWA 서비스워커 — 앱 셸 오프라인 캐시.
// 원칙:
//  - API 응답·config.js·크로스오리진은 캐시하지 않는다(민감/상태/호스트별 값).
//  - HTML 셸과 **JS 모듈은 network-first** — cache-first 면 배포해도 구버전 코드가
//    계속 실행되어 '고쳤는데 그대로'가 발생한다(과거 실제 사고).
//  - 아이콘·매니페스트 등 불변 자산만 cache-first.
// 배포 시 CACHE 버전을 올린다.
const CACHE = 'mhc-shell-v4';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(ASSETS.map((a) => c.add(a))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function networkFirst(req, fallbackKey) {
  return fetch(req).then((r) => {
    const copy = r.clone();
    caches.open(CACHE).then((c) => c.put(fallbackKey || req, copy)).catch(() => {});
    return r;
  }).catch(() => caches.match(fallbackKey || req));
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                                   // 변경요청은 항상 네트워크
  let url;
  try { url = new URL(req.url); } catch { return; }
  if (url.origin !== self.location.origin) return;                    // 크로스오리진(BFF·CDN) 미개입

  const path = url.pathname;
  if (/\/(auth|consent|chat|me|home|healthz|routine|diagnosis|facilities|persona)/.test(path)) return;
  if (path.endsWith('/config.js')) return;                            // 호스트별 주입값 — 항상 네트워크

  if (req.mode === 'navigate') {                                      // 셸: network-first
    e.respondWith(networkFirst(req, './index.html'));
    return;
  }
  if (path.endsWith('.js')) {                                         // JS 모듈: network-first
    e.respondWith(networkFirst(req));
    return;
  }
  e.respondWith(caches.match(req).then((c) => c || fetch(req)));       // 그 외 정적: cache-first
});
