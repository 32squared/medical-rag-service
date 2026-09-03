// app.js — 앱 루트. 탭 셸 + 라우팅 + 부팅 가드. 정본 §D-2(탭=순환 ①~⑥의 물리적 배치).
//
// 탭 배치 근거: 1번 탭이 '오늘의 행동(미완결 객체)'이어야 앱을 여는 이유가
// "질문이 생겨서"에서 "오늘 것이 아직 안 끝나서"로 바뀐다.

import { render } from 'preact';
import { useState, useEffect, useCallback } from 'preact/hooks';
import { GET, isLoggedIn, setTok } from './api.js';
import { html, Boundary, Loading, Fragment } from './ui.js';
import { Onboarding, PersonaPick, StartRoutine } from './onboard.js';
import { TodayTab } from './today.js';
import { ProgramTab, ReportView } from './program.js';
import { ChatTab } from './chat.js';
import { HealthTab, SettingsView, FinderView } from './health.js';
import { StatsView } from './stats.js';
import { RevealView } from './reveal.js';

const TABS = [
  { key: 'today', label: '오늘', icon: '✅' },
  { key: 'program', label: '프로그램', icon: '📅' },
  { key: 'chat', label: '상담', icon: '💬' },
  { key: 'health', label: '내 건강', icon: '🩺' },
];

function TabBar({ tab, onTab }) {
  return html`<nav class="tabbar" key="tabbar" role="tablist">
    ${TABS.map((t) => html`<button class=${'tabbtn' + (tab === t.key ? ' on' : '')}
      key=${t.key} role="tab" aria-selected=${tab === t.key} onClick=${() => onTab(t.key)}>
      <span class="tabicon" aria-hidden="true">${t.icon}</span>
      <span class="tablabel">${t.label}</span>
    </button>`)}
  </nav>`;
}

function App() {
  const [phase, setPhase] = useState('boot');   // boot | onboarding | persona | app
  const [tab, setTab] = useState('today');
  const [view, setView] = useState(null);       // null | report | settings | finder | start | stats | reveal
  const [viewArg, setViewArg] = useState({});
  const [prefill, setPrefill] = useState('');
  const [nonce, setNonce] = useState(0);        // 탭 강제 리마운트(데이터 새로고침)

  // 부팅: 토큰 → 페르소나 선택 여부 판정
  useEffect(() => {
    let alive = true;
    (async () => {
      if (!isLoggedIn()) { if (alive) setPhase('onboarding'); return; }
      const r = await GET('/persona');
      if (!alive) return;
      if (!r.ok) {
        if (r.kind === 'auth') { setTok(null); setPhase('onboarding'); return; }
        setPhase('app');                        // 네트워크 문제면 앱은 열고 화면별로 재시도
        return;
      }
      setPhase((r.data && r.data.persona) ? 'app' : 'persona');
    })();
    return () => { alive = false; };
  }, []);

  const go = useCallback((where, arg) => {
    if (where === 'today' || where === 'program' || where === 'chat' || where === 'health') {
      setView(null); setTab(where); return;
    }
    setViewArg(arg || {});
    setView(where);
  }, []);

  const onAsk = useCallback((q) => {
    setPrefill(String(q || ''));
    setView(null);
    setTab('chat');
  }, []);

  const backToApp = useCallback(() => { setView(null); setNonce((n) => n + 1); }, []);

  if (phase === 'boot') return html`<${Loading} label="불러오는 중…" />`;

  if (phase === 'onboarding') {
    return html`<${Boundary} name="onboarding">
      <${Onboarding} onDone=${() => setPhase('persona')} />
    </${Boundary}>`;
  }

  if (phase === 'persona') {
    return html`<${Boundary} name="persona">
      <${PersonaPick} onDone=${() => { setPhase('app'); setView('start'); }} />
    </${Boundary}>`;
  }

  // ── 전체화면 오버레이(탭바 숨김) ──
  if (view === 'start') {
    return html`<${Boundary} name="start" onHome=${backToApp}>
      <${StartRoutine} onStarted=${backToApp} onSkip=${backToApp} />
    </${Boundary}>`;
  }

  // ── 탭 화면 ──
  let body = null;
  if (view === 'report') {
    body = html`<${ReportView} week=${viewArg.week} go=${go} onAsk=${onAsk} />`;
  } else if (view === 'settings') {
    body = html`<${SettingsView} go=${go} onLoggedOut=${() => { setPhase('onboarding'); setView(null); }} />`;
  } else if (view === 'finder') {
    body = html`<${FinderView} go=${go} />`;
  } else if (view === 'stats') {
    body = html`<${StatsView} go=${go} date=${viewArg.date} />`;
  } else if (view === 'reveal') {
    body = html`<${RevealView} go=${go} date=${viewArg.date} />`;
  } else if (tab === 'today') {
    body = html`<${TodayTab} key=${'today' + nonce} go=${go} onAsk=${onAsk}
      onStart=${() => setView('start')} />`;
  } else if (tab === 'program') {
    body = html`<${ProgramTab} key=${'prog' + nonce} go=${go} />`;
  } else if (tab === 'chat') {
    body = html`<${ChatTab} prefill=${prefill} onConsumePrefill=${() => setPrefill('')} />`;
  } else {
    body = html`<${HealthTab} key=${'health' + nonce} go=${go} />`;
  }

  return html`<${Fragment}>
    <div class="screen" key="screen">
      <${Boundary} name=${view || tab} onHome=${backToApp}>${body}</${Boundary}>
    </div>
    <${TabBar} tab=${tab} onTab=${(t) => { setView(null); setTab(t); }} />
  </${Fragment}>`;
}

// ── 부팅 ─────────────────────────────────────────────────────────
function boot() {
  const root = document.getElementById('root');
  if (!root) return;
  try {
    root.innerHTML = '';
    render(html`<${Boundary} name="app"><${App} /></${Boundary}>`, root);
  } catch (e) {
    try { console.error('[boot]', e); } catch { /* noop */ }
    root.innerHTML = '<div class="pad"><div class="errbox">'
      + '<div class="errtitle">앱을 시작하지 못했습니다.</div>'
      + '<div class="muted" style="font-size:12.5px;margin-top:6px">새로고침 해주세요.</div>'
      + '</div></div>';
  }
}

try {
  window.addEventListener('error', (e) => { try { console.error('[window.error]', e.message); } catch { /* noop */ } });
  window.addEventListener('unhandledrejection', (e) => { try { console.error('[unhandled]', e.reason); } catch { /* noop */ } });
} catch { /* noop */ }

boot();

// PWA 서비스워커(실패해도 앱 동작에 영향 없음)
try {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
} catch { /* noop */ }
