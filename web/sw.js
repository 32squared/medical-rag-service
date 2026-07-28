// 마이헬스케어 PWA 서비스워커 — 앱 셸 오프라인 캐시(API 응답·config.js 는 캐시 금지).
// config.js(런타임 BFF URL)는 precache·cache 안 함 → 호스트별 주입값이 항상 네트워크 반영.
const CACHE = 'mhc-shell-v2';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                  // 변경요청은 항상 네트워크
  if (new URL(req.url).origin !== self.location.origin) return;  // 크로스오리진(BFF API·CDN)은 SW 미개입
  const path = new URL(req.url).pathname;
  // 인증·동의·채팅 등 BFF API 는 캐시하지 않음(민감/상태)
  if (/\/(auth|consent|chat|me|home|healthz)\b/.test(path)) return;
  // HTML 셸 네비게이션은 network-first(업데이트 즉시 반영) + 오프라인 시 캐시 폴백.
  // (cache-first 면 셸이 고착돼 배포 업데이트가 안 보임)
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).then((r) => {
        const copy = r.clone();
        caches.open(CACHE).then((c) => c.put('./index.html', copy));
        return r;
      }).catch(() => caches.match('./index.html'))
    );
    return;
  }
  e.respondWith(caches.match(req).then((c) => c || fetch(req)));  // 기타 정적자원 cache-first
});
