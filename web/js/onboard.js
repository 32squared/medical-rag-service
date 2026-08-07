// onboard.js — 첫 진입 여정. 정본 §C-1(F0~F5).
//   웰컴 → 동의 → 본인인증(mock) → 체험 프로필(②PHR 대체) → 상태 진단(③) → 트랙 선택 → 루틴 시작(④)
// 설계: 설명 화면을 늘리지 않는다. 선택지 = 결정 부담 = 이탈.

import { useState } from 'preact/hooks';
import { GET, GET_PUB, POST, POST_PUB, setTok, deviceIdentity, errText } from './api.js';
import {
  html, Header, Loading, ErrorView, useLoader, useLatest, arr, str, num,
} from './ui.js';

const ITEM_DESC = {
  personal_info: '서비스 이용을 위한 기본 개인정보',
  sensitive_info: '맞춤 안내를 위한 건강·검진 정보(민감)',
  cross_border: '국외 LLM 이용 시 개인정보 국외이전',
  location: '가까운 병원·약국 찾기(위치)',
  push: '루틴 리마인더 등 알림',
  phr_link: '공단 건강검진 연동',
};

// ── 1. 웰컴 + 동의 + 인증 ────────────────────────────────────────
export function Onboarding({ onDone }) {
  const [step, setStep] = useState(0);
  const [items, setItems] = useState([]);
  const [sel, setSel] = useState({ personal_info: true });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const race = useLatest();

  async function goConsent() {
    setStep(1); setErr('');
    const r = await GET_PUB('/consent/items');
    if (!race.alive()) return;
    if (!r.ok) { setErr(errText(r)); return; }
    setItems(arr(r.data && r.data.items));
  }

  async function finish() {
    setBusy(true); setErr('');
    try {
      const s = await POST_PUB('/auth/pass/start', {});
      if (!s.ok) { setErr(errText(s)); return; }
      const cb = await POST_PUB('/auth/pass/callback', {
        tx_id: (s.data || {}).tx_id, mock_identity: deviceIdentity(),
      });
      if (!cb.ok) { setErr(errText(cb)); return; }
      setTok(cb.data);
      for (const it of items) {
        if (it && (it.required || sel[it.item_key])) {
          await POST('/consent', { item_key: it.item_key, action: 'grant', source: 'onboarding' });
        }
      }
      onDone();
    } catch {
      setErr('처리하지 못했어요. 잠시 후 다시 시도해 주세요.');
    } finally {
      if (race.alive()) setBusy(false);
    }
  }

  if (step === 0) {
    return html`<div class="pad center" key="welcome">
      <div class="brand" style="font-size:26px"><span class="dot">+</span> 마이헬스케어</div>
      <p class="muted" style="margin-top:14px;line-height:1.7">
        하루 30초, <b>오늘의 행동 하나</b>부터.<br/>
        12주 동안 기록이 쌓이면 내 건강 패턴이 보이고,
        궁금한 건 근거와 함께 바로 물어볼 수 있어요.</p>
      <div style="height:24px"></div>
      <button class="btn" onClick=${goConsent}>시작하기</button>
      <p class="note">테스트용 프로토타입 · 합성 데이터 · 의료자문 아님</p>
    </div>`;
  }

  return html`<div class="pad" key="consent">
    <div class="stepdots"><b class="on"></b><b class="on"></b><b></b></div>
    <h1>이용 동의</h1>
    <p class="muted">필수 항목에 동의하면 시작할 수 있어요. 선택 항목은 언제든 바꿀 수 있습니다.</p>
    <div style="height:14px"></div>
    ${items.length ? html`<div class="card" key="citems">
      ${items.map((it) => html`<div class="row" key=${str(it.item_key)}>
        <div style="flex:1">
          <div style="font-weight:600">${str(it.title)}${it.required ? html`<span class="req">필수</span>` : null}</div>
          <div class="muted" style="font-size:12.5px">${ITEM_DESC[it.item_key] || ''}</div>
        </div>
        <div class=${'sw' + ((it.required || sel[it.item_key]) ? ' on' : '') + (it.required ? ' lock' : '')}
          role="switch" aria-checked=${!!(it.required || sel[it.item_key])}
          onClick=${() => { if (!it.required) setSel((s) => ({ ...s, [it.item_key]: !s[it.item_key] })); }}>
          <i></i></div>
      </div>`)}
    </div>` : html`<${Loading} key="cload" label="약관을 불러오는 중…" />`}
    ${err ? html`<div class="err" key="cerr">${err}</div>` : null}
    <div style="height:16px"></div>
    <button class="btn" disabled=${busy || !items.length} onClick=${finish}>
      ${busy ? '처리 중…' : '동의하고 시작하기'}</button>
    <p class="note">본인인증은 데모(mock)입니다. CI/DI 는 해시로만 저장되며 원문은 보관하지 않습니다.</p>
  </div>`;
}

// ── 2. 체험 프로필(②PHR 대체) ───────────────────────────────────
export function PersonaPick({ onDone }) {
  const L = useLoader(() => GET_PUB('/personas'), []);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');

  if (L.state === 'loading') return html`<div key="pl"><${Header} title="체험 프로필" /><${Loading} /></div>`;
  if (L.state === 'error') {
    return html`<div key="pe"><${Header} title="체험 프로필" />
      <${ErrorView} err=${L.err} text=${errText(L.err)} onRetry=${L.reload} /></div>`;
  }
  const list = arr((L.data || {}).personas);

  async function pick(p) {
    setBusy(str(p.id)); setErr('');
    const r = await POST('/persona/select', { persona_id: p.id });
    setBusy('');
    if (!r.ok) { setErr(errText(r)); return; }
    onDone();
  }

  return html`<div key="persona">
    <${Header} title="체험 프로필 선택" />
    <div class="scroll">
      <p class="muted" style="line-height:1.7">
        데모 체험을 위해 가상의 건강 프로필을 하나 골라주세요.
        선택한 프로필의 검진·측정 신호로 <b>내 상태에 맞는 루틴</b>이 만들어져요.
        (합성 데이터 · 실제 본인 정보 아님)</p>
      ${err ? html`<div class="err" key="perr">${err}</div>` : null}
      <div style="height:12px"></div>
      ${list.map((p) => html`<button class="card personacard" key=${str(p.id)}
          disabled=${!!busy} onClick=${() => pick(p)}>
        <div style="display:flex;gap:12px;align-items:center">
          <div style="font-size:30px">${str(p.emoji)}</div>
          <div style="flex:1;text-align:left">
            <div style="font-weight:700">${str(p.name)}</div>
            <div class="muted" style="font-size:12.5px">${str(p.profile)}</div>
          </div>
          <span class="muted">${busy === p.id ? '…' : '›'}</span>
        </div>
      </button>`)}
      <div class="bottompad"></div>
    </div>
  </div>`;
}

// ── 3. 상태 진단(③) + 트랙 선택 + 루틴 시작(④) ──────────────────
const TRACK_META = {
  diet: { emoji: '🥗', name: '식이 기록', desc: '식사 시각·짠맛 습관을 하루 30초로 남겨요' },
  exercise: { emoji: '🏃', name: '활동 기록', desc: '오늘 몸을 움직였는지 1탭으로 남겨요' },
  habit: { emoji: '🌙', name: '생활 리듬', desc: '취침 시각과 컨디션을 하루 30초로 남겨요' },
};

export function StartRoutine({ onStarted, onSkip }) {
  const D = useLoader(() => GET('/diagnosis'), []);
  const [track, setTrack] = useState(null);
  const [intake, setIntake] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const C = useLoader(() => GET('/coaching/config'), []);

  if (D.state === 'loading') return html`<div key="sl"><${Header} title="루틴 시작" /><${Loading} /></div>`;

  const d = (D.state === 'data' && D.data) || {};
  const rec = (d.recommended && typeof d.recommended === 'object') ? d.recommended : {};
  const recTrack = str(rec.track) || 'diet';
  const cfg = (C.state === 'data' && arr((C.data || {}).tracks)) || [];
  const qs = track ? arr((cfg.find((t) => t && t.key === track) || {}).intake) : [];
  const ready = !track ? false : qs.every((q) => intake[q.id]);

  async function start() {
    setBusy(true); setErr('');
    const r = await POST('/routine/start', { track, intake, focus: rec.focus || null });
    setBusy(false);
    if (!r.ok) { setErr(errText(r)); return; }
    onStarted();
  }

  if (!track) {
    return html`<div key="trackpick">
      <${Header} title="루틴 시작" />
      <div class="scroll">
        ${d.band ? html`<div class="dgcard" key="dg">
          <div class="dgtop"><div class="dgband">${str(d.band)} 구간</div></div>
          ${arr(d.items).length ? html`<div class="dgitems" key="di">
            ${arr(d.items).map((it) => html`<div class="dgrow" key=${str(it.key)}>
              <span>${str(it.label)}</span>
              <span class=${'dgstate s-' + (str(it.state) || 'none')}>${str(it.state)}</span>
            </div>`)}</div>` : null}
          <div class="dgnotice">${str(d.notice)}</div>
        </div>` : null}

        <div class="sectitle" key="t1" style="margin-top:14px">어떤 기록부터 시작할까요?</div>
        <p class="muted" style="font-size:12.5px;margin-bottom:10px">
          12주 동안 매일 30초. 언제든 바꿀 수 있어요.</p>
        ${Object.keys(TRACK_META).map((k) => html`<button class="card trackcard2" key=${k}
            onClick=${() => setTrack(k)}>
          <div class="tkemoji">${TRACK_META[k].emoji}</div>
          <div class="tkbody">
            <div class="tkname">${TRACK_META[k].name}
              ${k === recTrack ? html`<span class="rectag" key="r">추천</span>` : null}</div>
            <div class="tkdesc">${TRACK_META[k].desc}</div>
          </div>
          <span class="muted">›</span>
        </button>`)}
        ${onSkip ? html`<button class="btn ghost" key="skip" style="margin-top:12px"
          onClick=${onSkip}>나중에 하기</button>` : null}
        <div class="bottompad"></div>
      </div>
    </div>`;
  }

  return html`<div key="intake">
    <${Header} title=${TRACK_META[track].name} onBack=${() => { setTrack(null); setIntake({}); }} />
    <div class="scroll">
      <p class="muted" style="line-height:1.7">몇 가지만 알려주시면 12주 루틴을 만들어 드려요.</p>
      <div style="height:10px"></div>
      ${qs.length ? qs.map((q) => html`<div class="card" key=${str(q.id)} style="margin-bottom:10px">
        <div style="font-size:14px;margin-bottom:8px">${str(q.q)}</div>
        <div class="chips">
          ${arr(q.options).map((o) => html`<button class=${'chip' + (intake[q.id] === o ? ' sel' : '')}
            key=${o} onClick=${() => setIntake((s) => ({ ...s, [q.id]: o }))}>${o}</button>`)}
        </div>
      </div>`) : html`<div class="muted" key="noq" style="font-size:13px">바로 시작할 수 있어요.</div>`}
      ${err ? html`<div class="err" key="serr">${err}</div>` : null}
      <button class="btn" key="go" style="margin-top:8px"
        disabled=${busy || (qs.length > 0 && !ready)} onClick=${start}>
        ${busy ? '만드는 중…' : '12주 루틴 시작하기'}</button>
      <div class="bottompad"></div>
    </div>
  </div>`;
}
