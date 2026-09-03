// ui.js — 공통 UI 프리미티브. 정본 §H-1(1,3,4,5,6) · §G.
//
// 안전 규칙:
//  - Boundary: App 전체 + 화면 단위 이중 적용(화면이 죽어도 탭바로 탈출 가능).
//  - 4상태(loading/error/empty/data) 전부에 헤더를 그린다 — 헤더 없는 early return 금지.
//  - 빈 슬롯은 null 로 통일. `${n && html`…`}` 는 n===0 일 때 '0' 이 렌더되므로 금지.

import { h, Fragment, Component } from 'preact';
import { useRef, useEffect, useState } from 'preact/hooks';
import htm from 'htm';

export const html = htm.bind(h);
export { Fragment };

// ── ErrorBoundary ────────────────────────────────────────────────
export class Boundary extends Component {
  static getDerivedStateFromError(err) { return { err }; }
  componentDidCatch(err, info) {
    try { console.error('[boundary]', this.props.name || '?', err, info); } catch { /* noop */ }
  }
  render() {
    if (this.state && this.state.err) {
      return html`<div class="pad">
        <div class="errbox">
          <div class="errtitle">화면을 표시하지 못했습니다.</div>
          <div class="muted" style="font-size:12.5px;margin-top:4px">잠시 후 다시 시도해 주세요.</div>
          <button class="btn ghost" style="margin-top:12px"
            onClick=${() => this.setState({ err: null })}>다시 시도</button>
          ${this.props.onHome ? html`<button class="btn ghost" style="margin-top:8px"
            onClick=${this.props.onHome}>홈으로</button>` : null}
        </div>
      </div>`;
    }
    return this.props.children;
  }
}

// ── 경합 가드(스펙 H-1.6) ────────────────────────────────────────
export function useLatest() {
  const seq = useRef(0);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  return {
    begin: () => ++seq.current,
    accept: (id) => alive.current && id === seq.current,
    alive: () => alive.current,
  };
}

/** 표준 로더 — {state:'loading'|'error'|'data', data, err, reload} */
export function useLoader(fetcher, deps) {
  const [st, setSt] = useState({ state: 'loading', data: null, err: null });
  const race = useLatest();
  const fRef = useRef(fetcher);
  fRef.current = fetcher;
  const run = useRef(null);
  run.current = async () => {
    const id = race.begin();
    setSt((s) => ({ ...s, state: s.data ? s.state : 'loading' }));
    let r;
    try { r = await fRef.current(); } catch { r = { ok: false, kind: 'network' }; }
    if (!race.accept(id)) return;
    if (r && r.ok) setSt({ state: 'data', data: r.data, err: null });
    else setSt((s) => ({ state: s.data ? 'data' : 'error', data: s.data, err: r }));
  };
  useEffect(() => { run.current(); }, deps || []);
  return { ...st, reload: () => run.current() };
}

// ── 헤더 ─────────────────────────────────────────────────────────
export function Header({ title, onBack, right }) {
  return html`<div class="hdr">
    ${onBack
      ? html`<button class="icobtn" key="back" onClick=${onBack} aria-label="뒤로">‹</button>`
      : html`<span class="hdrspacer" key="back"></span>`}
    <div class="hdrtitle">${title || ''}</div>
    <div class="hdrright" key="right">${right || null}</div>
  </div>`;
}

export function Loading({ label }) {
  return html`<div class="pad center" key="loading">
    <div class="spinner" aria-hidden="true"></div>
    <p class="muted" style="margin-top:10px">${label || '불러오는 중…'}</p>
  </div>`;
}

export function ErrorView({ err, onRetry, text }) {
  return html`<div class="pad" key="errorview">
    <div class="errbox">
      <div class="errtitle">${text || '지금은 불러오지 못했어요.'}</div>
      ${onRetry ? html`<button class="btn ghost" style="margin-top:12px" onClick=${onRetry}>다시 시도</button>` : null}
    </div>
  </div>`;
}

export function Empty({ title, desc, cta, onCta }) {
  return html`<div class="pad" key="empty">
    <div class="emptybox">
      <div class="emptytitle">${title || ''}</div>
      ${desc ? html`<div class="muted" style="font-size:13px;margin-top:6px;line-height:1.6">${desc}</div>` : null}
      ${cta ? html`<button class="btn" style="margin-top:16px" onClick=${onCta}>${cta}</button>` : null}
    </div>
  </div>`;
}

// ── 안전 정규화(스펙 H-1.4) ──────────────────────────────────────
export const arr = (v) => (Array.isArray(v) ? v : []);
export const num = (v, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);
export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, num(v, lo)));
export const str = (v, d = '') => (typeof v === 'string' ? v : d);

/** tracks 블록(서버 파생값). awake/complete 를 프론트에서 재계산하지 않는다. */
export function normTracks(t) {
  const x = t && typeof t === 'object' ? t : {};
  const w = x.water || {}; const s = x.steps || {}; const m = x.mind || {};
  return {
    water: { cups: clamp(w.cups, 0, 8), goal: num(w.goal, 6), awake: !!w.awake, complete: !!w.complete },
    steps: { value: s.value == null ? null : num(s.value), goal: num(s.goal, 6000), source: str(s.source, 'none'),
      stale: !!s.stale, awake: !!s.awake, complete: !!s.complete },
    mind: { seconds: num(m.seconds), sessions: num(m.sessions), awake: !!m.awake, complete: !!m.complete },
  };
}

/** /routine/today 응답 → 렌더 안전 형태. 원본을 직접 렌더하지 않는다. */
export function normToday(raw) {
  const r = raw || {};
  const p = r.program || null;
  return {
    serverDate: str(r.server_date),
    state: str(r.state, 'S1_NEW'),
    program: p ? {
      id: str(p.program_id), track: str(p.track, 'diet'),
      week: clamp(p.week_no, 1, 12), day: num(p.day_no, 1),
      phase: str(p.phase), theme: str(p.theme), mission: str(p.mission),
      goalDays: num(p.goal_days, 3), itemCap: num(p.item_cap, 0),
      status: str(p.status, 'active'), weeksTotal: num(p.weeks_total, 12),
    } : null,
    today: r.today ? {
      id: str(r.today.id || r.today.action_id),
      text: str(r.today.text), cite: str(r.today.cite),
      minutes: num(r.today.minutes, 1),
      input: (r.today.input && typeof r.today.input === 'object')
        ? { kind: str(r.today.input.kind, 'tap'), options: arr(r.today.input.options) }
        : { kind: 'tap', options: [] },
      status: str(r.today.status, 'pending'),
      value: r.today.value == null ? null : str(r.today.value),
    } : null,
    support: arr(r.support).map((s) => ({
      key: str(s && s.key), text: str(s && s.text), cite: str(s && s.cite),
      status: str(s && s.status, 'pending'),
    })).filter((s) => s.text),
    week: r.week ? {
      w: clamp(r.week.w, 1, 12), done: num(r.week.done_days), goal: num(r.week.goal_days, 1),
      adherence: clamp(r.week.adherence, 0, 100), na: num(r.week.na_days),
    } : null,
    weeks: arr(r.weeks).map((w) => ({
      w: clamp(w && w.w, 1, 12), state: str(w && w.state, 'future'),
      done: num(w && w.done_days), goal: num(w && w.goal_days, 1),
    })),
    weekDays: arr(r.week_days).map((d) => ({
      date: str(d && d.date), weekday: str(d && d.weekday), state: str(d && d.state, 'future'),
    })),
    days: arr(r.days).map((d) => ({ date: str(d && d.date), level: clamp(d && d.level, 0, 2) })),
    stats: {
      streak: 0, best_streak: 0, done: 0, adherence: 0, points: 0, level: 1,
      badges: [], days_since_last: 0, ...(r.stats && typeof r.stats === 'object' ? r.stats : {}),
    },
    coach: r.coach && typeof r.coach === 'object'
      ? { action: str(r.coach.action), message: str(r.coach.message) } : null,
    band: r.band == null ? null : str(r.band),
    banner: r.banner == null ? null : str(r.banner),
    // 응급(kind=emergency)만 화면 차단. safety.fun_layer 는 재미 레이어 게이트(02-dev-requirements §4-1).
    safety: r.safety && typeof r.safety === 'object' && (r.safety.kind === 'emergency' || r.safety.text)
      ? { kind: str(r.safety.kind), text: str(r.safety.text), referral: str(r.safety.referral) } : null,
    funLayer: !!(r.safety && typeof r.safety === 'object' && r.safety.fun_layer),
    tracks: normTracks(r.tracks),
    archetype: {
      preview: r.archetype && r.archetype.preview ? str(r.archetype.preview) : null,
      completedCount: clamp(r.archetype && r.archetype.completed_count, 0, 3),
      seenToday: !!(r.archetype && r.archetype.seen_today),
    },
    chips: arr(r.ask_chips).filter((x) => typeof x === 'string'),
    reportDue: r.report_due && r.report_due.week ? { week: clamp(r.report_due.week, 1, 12) } : null,
    notify: r.notify && typeof r.notify === 'object'
      ? { hhmm: r.notify.hhmm == null ? null : str(r.notify.hhmm) } : { hhmm: null },
    evidence: r.evidence && r.evidence.label ? { label: str(r.evidence.label) } : null,
    previewWeeks: arr(r.preview_weeks),
    personalization: !!r.personalization,
  };
}
