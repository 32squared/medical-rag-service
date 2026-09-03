// tracks.js — 오늘 탭의 3트랙 타일(물·걸음·마음) + 입력 시트 + 아키타입 티저 + 기록 보기 CTA.
// 정본: docs/design/todays-me-mockups/spec-01-daily-tracker.md §2-3·§3-2, 02-dev-requirements FR-T1-02~07.
//
// 규칙:
//  - awake/complete 는 서버 파생값만 렌더한다(프론트 자체 판정 금지).
//  - 미완료 카운트("2개 남음")·붉은색·실패 어휘를 쓰지 않는다. 티저는 이미 한 것만 말한다.
//  - 오프라인이면 입력을 큐에 넣고(idempotency_key) 온라인 복귀 시 재전송한다.

import { useState, useEffect, useRef } from 'preact/hooks';
import { PUT, LS, uuid } from './api.js';
import { html, num } from './ui.js';
import { elementSvg, ICON, ARCHETYPES } from './archetypes.js';

const QK = 'mhc_metrics_q';

// ── 지표 전송(오프라인 큐) ────────────────────────────────────────
export async function putMetrics(body) {
  const payload = { ...body, client_ts: new Date().toISOString(), idempotency_key: uuid() };
  const r = await PUT('/metrics/today', payload);
  if (!r.ok && r.kind === 'network') {
    const q = LS.getJSON(QK) || [];
    q.push(payload);
    LS.setJSON(QK, q.slice(-20));
    return { ok: true, queued: true };
  }
  return r;
}

export async function flushMetricsQueue() {
  const q = LS.getJSON(QK) || [];
  if (!q.length) return false;
  const rest = [];
  for (const p of q) {
    const r = await PUT('/metrics/today', p);
    if (!r.ok && r.kind === 'network') rest.push(p);
  }
  LS.setJSON(QK, rest);
  return rest.length < q.length;
}

try { window.addEventListener('online', () => { flushMetricsQueue().catch(() => {}); }); } catch { /* noop */ }

// ── 바텀시트 ─────────────────────────────────────────────────────
function Sheet({ title, onClose, children }) {
  return html`<div class="fl-sheetwrap" key="sheet" role="dialog" aria-modal="true" aria-label=${title}>
    <div class="fl-sheetbg" onClick=${onClose}></div>
    <div class="fl-sheet">
      <div class="fl-sheethead">
        <div class="fl-sheettitle">${title}</div>
        <button class="fl-icobtn" aria-label="닫기" onClick=${onClose}
          dangerouslySetInnerHTML=${{ __html: ICON.close() }}></button>
      </div>
      ${children}
    </div>
  </div>`;
}

// 물: 8칸 컵 그리드. 컵 n 탭 → n컵, 마지막 채운 컵 다시 탭 → 하나 줄이기.
function CupSheet({ cups, goal, onClose, onSave }) {
  const [n, setN] = useState(num(cups));
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    await onSave({ water_cups: n });
    setBusy(false); onClose();
  }
  return html`<${Sheet} title="오늘 마신 물" onClose=${onClose}>
    <div class="fl-cupgrid">
      ${[1, 2, 3, 4, 5, 6, 7, 8].map((i) => html`<button class="fl-cupbtn" key=${i}
        aria-label=${`${i}컵`} aria-pressed=${i <= n}
        onClick=${() => setN(i === n ? i - 1 : i)}
        dangerouslySetInnerHTML=${{ __html: i <= n ? ICON.cup('#4C86F0', 40) : ICON.cupEmpty(40) }}></button>`)}
    </div>
    <div class="fl-sheetnote">${n}컵 · 1컵 200mL${n >= goal ? ' · 오늘 물은 채웠어요' : ''}</div>
    <button class="fl-cta" disabled=${busy} onClick=${save}>
      <span>${busy ? '기록 중…' : '기록하기'}</span>
      <span dangerouslySetInnerHTML=${{ __html: ICON.arrow() }}></span>
    </button>
  </${Sheet}>`;
}

// 걸음: v1 수동 입력(PWA 는 헬스 연동 불가 — 04-integration-plan D2).
function StepsSheet({ value, goal, onClose, onSave }) {
  const [v, setV] = useState(num(value));
  const [busy, setBusy] = useState(false);
  const step = (d) => setV((x) => Math.max(0, Math.min(200000, x + d)));
  async function save(confirmed) {
    setBusy(true);
    await onSave({ steps: v, steps_source: 'manual', steps_confirmed: !!confirmed });
    setBusy(false); onClose();
  }
  return html`<${Sheet} title="오늘 걸음" onClose=${onClose}>
    <div class="fl-stepper">
      <button class="fl-stepbtn" aria-label="1000 줄이기" onClick=${() => step(-1000)}>−</button>
      <input class="fl-stepinput" type="number" inputmode="numeric" min="0" max="200000" step="100"
        value=${v} onInput=${(e) => setV(Math.max(0, Math.min(200000, num(e.target.value))))} />
      <button class="fl-stepbtn" aria-label="1000 늘리기" onClick=${() => step(1000)}>+</button>
    </div>
    <div class="fl-sheetnote">걸음 수를 직접 적어요${v >= goal ? ' · 오늘 활동은 채웠어요' : ''}</div>
    <button class="fl-cta" disabled=${busy} onClick=${() => save(false)}>
      <span>${busy ? '기록 중…' : '기록하기'}</span>
      <span dangerouslySetInnerHTML=${{ __html: ICON.arrow() }}></span>
    </button>
    <button class="fl-textbtn" disabled=${busy} onClick=${() => save(true)}>걸음 대신 활동 완료로 기록</button>
  </${Sheet}>`;
}

// 마음: 1분 원형 타이머. 완주(60초)만 세션. 중단 시 진행분 미저장.
function MindSheet({ onClose, onSave }) {
  const [left, setLeft] = useState(60);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  function start() {
    if (running) return;
    setRunning(true);
    timer.current = setInterval(() => {
      setLeft((x) => {
        if (x <= 1) { clearInterval(timer.current); timer.current = null; finish(); return 0; }
        return x - 1;
      });
    }, 1000);
  }
  async function finish() {
    setBusy(true);
    await onSave({ mind_session_completed: true, mind_seconds: 60 });
    setBusy(false); onClose();
  }
  function stop() { if (timer.current) clearInterval(timer.current); onClose(); }
  const pct = (60 - left) / 60;
  const R = 44; const C = 2 * Math.PI * R;
  return html`<${Sheet} title="1분 마음챙김" onClose=${stop}>
    <div class="fl-timerwrap">
      <svg width="120" height="120" viewBox="0 0 120 120" aria-hidden="true">
        <circle cx="60" cy="60" r=${R} fill="none" stroke="#EFE6D6" stroke-width="12"/>
        <circle cx="60" cy="60" r=${R} fill="none" stroke="#8E7BEF" stroke-width="12" stroke-linecap="round"
          stroke-dasharray=${C} stroke-dashoffset=${C * (1 - pct)} transform="rotate(-90 60 60)"/>
      </svg>
      <div class="fl-timernum lex" aria-live="polite">${left}</div>
    </div>
    <div class="fl-sheetnote">${running ? '숨에만 집중해요' : '시작하면 1분 뒤에 자동으로 기록돼요'}</div>
    ${running
      ? html`<button class="fl-textbtn" key="stop" disabled=${busy} onClick=${stop}>오늘은 여기까지</button>`
      : html`<button class="fl-cta" key="start" onClick=${start}>
          <span>시작하기</span><span dangerouslySetInnerHTML=${{ __html: ICON.arrow() }}></span></button>`}
  </${Sheet}>`;
}

// ── 트랙 타일 3개 ──────────────────────────────────────────────
function Tile({ kind, bg, label, caption, awake, complete, funLayer, onOpen }) {
  const state = funLayer ? (awake ? 'awake' : 'sleep') : 'plain';
  return html`<button class=${'fl-tile' + (awake ? ' fl-tile-awake' : '')} style=${`background:${bg}`}
    onClick=${onOpen} aria-label=${`${label} 입력`}>
    ${funLayer ? html`<span class=${'fl-badge' + (complete ? ' on' : '')} aria-hidden="true"
      dangerouslySetInnerHTML=${{ __html: complete ? ICON.star('#FFD84D', 16) : '' }}></span>` : null}
    <span class="fl-tilechar" dangerouslySetInnerHTML=${{ __html: elementSvg(kind, state, 44) }}></span>
    <span class="fl-tilelabel jua">${label}</span>
    <span class="fl-tilecap">${caption}</span>
  </button>`;
}

export function TrackTiles({ tracks, funLayer, onChanged }) {
  const [sheet, setSheet] = useState(null);       // null | water | steps | mind
  const [note, setNote] = useState('');
  const t = tracks || {};
  const w = t.water || {}; const s = t.steps || {}; const m = t.mind || {};

  async function save(body) {
    const r = await putMetrics(body);
    if (!r.ok) { setNote('지금은 기록하지 못했어요. 잠시 후 다시 시도해 주세요.'); return; }
    setNote(r.queued ? '연결되면 자동으로 기록돼요.' : '');
    if (onChanged) await onChanged(r.data || null);
  }

  const stepsCap = s.value == null
    ? '탭해서 적기'
    : (s.stale ? '걸음은 조금 뒤에 들어와요' : `${num(s.value).toLocaleString()}걸음`);

  return html`<div class="fl-tiles" key="tiles">
    <div class="fl-tilerow">
      <${Tile} kind="water" bg="#AFC9F5" label="물" funLayer=${funLayer}
        caption=${w.cups > 0 ? `${w.cups}컵째${w.complete ? ' · 완료' : ''}` : '자는 중'}
        awake=${!!w.awake} complete=${!!w.complete} onOpen=${() => setSheet('water')} />
      <${Tile} kind="bolt" bg="#FFF3D6" label="걸음" funLayer=${funLayer}
        caption=${s.awake ? stepsCap : (s.value == null ? '자는 중' : stepsCap)}
        awake=${!!s.awake} complete=${!!s.complete} onOpen=${() => setSheet('steps')} />
      <${Tile} kind="moon" bg="#CDBFF7" label="마음" funLayer=${funLayer}
        caption=${m.sessions > 0 ? `${Math.max(1, Math.floor(num(m.seconds) / 60))}분 · 완료` : (m.awake ? '깨어 있음' : '자는 중')}
        awake=${!!m.awake} complete=${!!m.complete} onOpen=${() => setSheet('mind')} />
    </div>
    ${note ? html`<div class="fl-note" key="note">${note}</div>` : null}
    ${sheet === 'water' ? html`<${CupSheet} cups=${w.cups} goal=${w.goal || 6} onClose=${() => setSheet(null)} onSave=${save} />` : null}
    ${sheet === 'steps' ? html`<${StepsSheet} value=${s.value} goal=${s.goal || 6000} onClose=${() => setSheet(null)} onSave=${save} />` : null}
    ${sheet === 'mind' ? html`<${MindSheet} onClose=${() => setSheet(null)} onSave=${save} />` : null}
  </div>`;
}

// ── 아키타입 티저(이미 한 것만 말한다) ─────────────────────────────
export function ArchetypeTeaser({ tracks, archetype }) {
  const t = tracks || {};
  const awake = [t.water && t.water.awake && '물방울', t.steps && t.steps.awake && '번개', t.mind && t.mind.awake && '달'].filter(Boolean);
  const a = archetype || {};
  let text;
  if (a.preview && ARCHETYPES[a.preview]) text = `${ARCHETYPES[a.preview].nameKo}이(가) 깨어났어요`;
  else if (awake.length) text = `지금 깨어나는 중… ${awake.join('·')}이 반짝여요`;
  else text = '오늘 하나만 남기면 캐릭터가 깨어나요';
  return html`<div class="fl-teaser" key="teaser">
    <span class="fl-teaserq lex">?</span>
    <span class="fl-teasertext"><span class="fl-teaserlabel">오늘의 캐릭터</span>${text}</span>
  </div>`;
}

export function StatsCTA({ enabled, onOpen }) {
  return html`<button class=${'fl-cta' + (enabled ? '' : ' fl-cta-off')} key="statscta"
    aria-disabled=${!enabled} onClick=${() => { if (enabled) onOpen(); }}>
    <span>오늘의 기록 보기</span>
    <span dangerouslySetInnerHTML=${{ __html: ICON.arrow(enabled ? '#FFD84D' : '#7A7A7A') }}></span>
  </button>`;
}
