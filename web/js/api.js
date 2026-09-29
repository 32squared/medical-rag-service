// api.js — BFF 클라이언트. 정본 docs/plan/25-routine-transition-spec.md §H-1(2,7,8).
//
// 안전 규칙:
//  - 브라우저 API는 전부 try/catch 래퍼. 모듈 최상위에서 localStorage 를 직접 읽지 않는다
//    (iOS Safari 제한 환경에서 SecurityError 가 모듈 평가를 깨 앱 전체가 백지가 된다).
//  - getJSON 은 ok → content-type → json 3단 검사. 화면 코드에서 r.json() 직접 호출 금지.
//  - refresh 는 싱글플라이트. BFF refresh 는 1회용 회전이라 병렬 호출이 겹치면
//    확정적으로 로그아웃된다.

const _mem = new Map();

export const LS = {
  get(k) { try { return localStorage.getItem(k); } catch { return _mem.has(k) ? _mem.get(k) : null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { _mem.set(k, v); } },
  del(k) { try { localStorage.removeItem(k); } catch { _mem.delete(k); } },
  getJSON(k) { try { return JSON.parse(LS.get(k) || 'null'); } catch { return null; } },
  setJSON(k, v) { try { LS.set(k, JSON.stringify(v)); } catch { /* noop */ } },
};

const TK = 'mhc_tokens';

function bffBase() {
  let injected = '';
  try { injected = window.__MHC_BFF__ || ''; } catch { injected = ''; }
  return String(LS.get('mhc_bff') || injected || '').replace(/\/$/, '');
}

export const getTok = () => LS.getJSON(TK);
export const setTok = (t) => (t ? LS.setJSON(TK, t) : LS.del(TK));
export const isLoggedIn = () => !!(getTok() || {}).access_token;

// ── refresh 싱글플라이트 ──────────────────────────────────────────
let _refreshing = null;

async function _doRefresh() {
  const t = getTok();
  if (!t || !t.refresh_token) return false;
  let r;
  try {
    r = await fetch(bffBase() + '/auth/refresh', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: t.session_id, refresh_token: t.refresh_token }),
    });
  } catch { return false; }              // 네트워크 실패는 로그아웃 사유가 아니다
  if (!r.ok) { if (r.status === 401) setTok(null); return false; }
  let d;
  try { d = await r.json(); } catch { return false; }
  const cur = getTok() || t;             // 저장 직전 최신 스냅샷 재확인
  setTok({ ...cur, access_token: d.access_token, refresh_token: d.refresh_token });
  return true;
}

export function refresh() {
  if (!_refreshing) _refreshing = _doRefresh().finally(() => { _refreshing = null; });
  return _refreshing;
}

// ── 저수준 fetch ─────────────────────────────────────────────────
async function rawFetch(path, { method = 'GET', body, auth = true, retry = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  const t = getTok();
  if (auth && t && t.access_token) headers['Authorization'] = 'Bearer ' + t.access_token;
  const res = await fetch(bffBase() + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && auth && retry) {
    const ok = await refresh();
    if (ok) return rawFetch(path, { method, body, auth, retry: false });
  }
  return res;
}

/** 표준 결과: {ok:true,data} | {ok:false,kind:'network'|'auth'|'consent'|'server'|'shape',status?,data?} */
export async function getJSON(path, opts = {}) {
  let res;
  try { res = await rawFetch(path, opts); } catch { return { ok: false, kind: 'network' }; }
  if (res.status === 401) return { ok: false, kind: 'auth' };
  if (res.status === 403) return { ok: false, kind: 'consent' };
  if (!res.ok) {
    let d = null;
    try { d = await res.json(); } catch { d = null; }
    return { ok: false, kind: 'server', status: res.status, data: d };
  }
  const ct = (res.headers && res.headers.get('content-type')) || '';
  if (ct.indexOf('json') < 0) return { ok: false, kind: 'shape' };
  try { return { ok: true, data: await res.json() }; } catch { return { ok: false, kind: 'shape' }; }
}

export const GET = (p) => getJSON(p);
export const POST = (p, body) => getJSON(p, { method: 'POST', body: body || {} });
export const PUT = (p, body) => getJSON(p, { method: 'PUT', body: body || {} });
export const DEL = (p) => getJSON(p, { method: 'DELETE' });
export const POST_PUB = (p, body) => getJSON(p, { method: 'POST', body: body || {}, auth: false });
export const GET_PUB = (p) => getJSON(p, { auth: false });

// ── 오류 → 한국어(스펙 F-7). 단일 테이블. ────────────────────────
const ERR_TEXT = {
  network: '연결이 불안정해요.',
  auth: '다시 로그인해주세요.',
  consent: '개인정보 이용 동의가 필요해요.',
  server: '지금은 불러오지 못했어요.',
  shape: '지금은 불러오지 못했어요.',
};
const DETAIL_TEXT = {
  program_exists: '이미 진행 중인 루틴이 있어요.',
  activation_lock: '3일 정착 후에 항목을 늘릴 수 있어요.',
  cap_reached: '이번 주는 여기까지가 좋아요.',
  advance_blocked_band: '지금 구간에서는 늘리지 않는 편이 안전해요.',
  notify_time_not_allowed: '알림은 08시~20시 사이로 정해주세요.',
  unknown_track: '선택한 트랙을 찾지 못했어요.',
  unknown_pack: '선택한 루틴을 찾지 못했어요.',
  clearance_required: '지금 구간에서는 이 루틴보다 진료 상담이 먼저예요.',
  emergency_block: '지금은 루틴보다 진료가 먼저예요.',
  no_program: '진행 중인 루틴이 없어요.',
  personal_info_consent_required: '개인정보 이용 동의가 필요해요.',
  band_gate: '지금은 기록만 남겨둘게요.',
  invalid_value: '입력값을 다시 확인해 주세요.',
  no_archetype: '오늘은 아직 캐릭터가 없어요.',
  locked: '이 카드는 더 이상 고칠 수 없어요.',
  comment_too_long: '한 줄 코멘트는 20자까지예요.',
};

export function errText(r) {
  if (!r || r.ok) return '';
  const detail = r.data && r.data.detail;
  if (typeof detail === 'string' && DETAIL_TEXT[detail]) return DETAIL_TEXT[detail];
  return ERR_TEXT[r.kind] || '지금은 불러오지 못했어요.';
}

// ── 기기 고정 데모 식별자 ────────────────────────────────────────
export function deviceIdentity() {
  let v = LS.get('mhc_devid');
  if (!v) {
    v = 'mhc-' + Math.random().toString(36).slice(2, 11);
    LS.set('mhc_devid', v);
  }
  return v;
}

export function uuid() {
  try {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
  } catch { /* noop */ }
  return 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}
