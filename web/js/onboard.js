// onboard.js — 첫 진입 여정. 정본 §C-1(F0~F5).
//   웰컴 → 동의 → 본인인증(mock) → 체험 프로필(②PHR 대체) → 상태 진단(③) → 루틴·트랙 선택 → 루틴 시작(④)
// 설계: 설명 화면을 늘리지 않는다. 선택지 = 결정 부담 = 이탈.

import { useState } from 'preact/hooks';
import { GET, GET_PUB, POST, POST_PUB, setTok, deviceIdentity, errText } from './api.js';
import {
  html, Header, Loading, ErrorView, useLoader, useLatest, normPack, arr, str, num,
} from './ui.js';
import { iconOf } from './archetypes.js';

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
        기록이 쌓이면 내 패턴이 보이고,
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

// ── 3. 상태 진단(③) + 루틴 고르기 + 트랙 선택 + 루틴 시작(④) ─────────
// 루틴은 팩(routines/packs/*)에서 온다(28 FR-F1). 팩이 하나면 고르기 화면을 건너뛴다.
// 트랙이 하나면 트랙 화면도 건너뛴다. 문진은 label 을 보여주고 value 를 보낸다.
const GATE_TEXT = {
  clearance_required: '지금 구간에서는 진료 상담 뒤에 시작해요',
  emergency_block: '지금은 루틴보다 진료가 먼저예요',
};

function Icon({ k }) {
  return html`<div class="tkemoji" aria-hidden="true"
    dangerouslySetInnerHTML=${{ __html: iconOf(k, '#141414', 26) }}></div>`;
}

export function StartRoutine({ onStarted, onSkip }) {
  const D = useLoader(() => GET('/diagnosis'), []);
  const P = useLoader(() => GET('/routine/packs'), []);
  const [packId, setPackId] = useState(null);
  const [track, setTrack] = useState(null);
  const [intake, setIntake] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  if (D.state === 'loading' || P.state === 'loading') {
    return html`<div key="sl"><${Header} title="루틴 시작" /><${Loading} /></div>`;
  }
  if (P.state === 'error') {
    return html`<div key="spe"><${Header} title="루틴 시작" />
      <${ErrorView} err=${P.err} text=${errText(P.err)} onRetry=${P.reload} /></div>`;
  }

  const d = (D.state === 'data' && D.data) || {};
  const rec = (d.recommended && typeof d.recommended === 'object') ? d.recommended : {};
  const packs = arr((P.data || {}).packs).map(normPack).filter((x) => x.tracks.length);
  const single = packs.length === 1;
  const pk = packs.find((x) => x.id === packId) || (single ? packs[0] : null);
  const tr = pk && (pk.tracks.find((t) => t.id === track) || (pk.tracks.length === 1 ? pk.tracks[0] : null));
  const qs = tr ? tr.intake : [];
  const ready = qs.every((q) => intake[q.id]);

  function back() {
    setErr(''); setIntake({});
    if (tr && pk.tracks.length > 1) { setTrack(null); return; }
    setTrack(null); setPackId(null);
  }

  async function start() {
    setBusy(true); setErr('');
    const r = await POST('/routine/start', {
      pack_id: pk.id, track: tr.id, intake,
      focus: pk.recommended ? (rec.focus || null) : null,
    });
    setBusy(false);
    if (!r.ok) { setErr(errText(r)); return; }
    onStarted();
  }

  const diag = d.band ? html`<div class="dgcard" key="dg">
    <div class="dgtop"><div class="dgband">${str(d.band)} 구간</div></div>
    ${arr(d.items).length ? html`<div class="dgitems" key="di">
      ${arr(d.items).map((it) => html`<div class="dgrow" key=${str(it.key)}>
        <span>${str(it.label)}</span>
        <span class=${'dgstate s-' + (str(it.state) || 'none')}>${str(it.state)}</span>
      </div>`)}</div>` : null}
    <div class="dgnotice">${str(d.notice)}</div>
  </div>` : null;
  const skip = onSkip ? html`<button class="btn ghost" key="skip" style="margin-top:12px"
    onClick=${onSkip}>나중에 하기</button>` : null;

  // ① 루틴 고르기
  if (!pk) {
    return html`<div key="packpick">
      <${Header} title="루틴 고르기" />
      <div class="scroll">
        ${diag}
        <div class="sectitle" key="t0" style="margin-top:14px">어떤 루틴을 시작할까요?</div>
        <p class="muted" style="font-size:12.5px;margin-bottom:10px">
          하루 한 가지씩. 진행 중인 루틴은 하나만 둘 수 있어요.</p>
        ${packs.map((x) => html`<button class=${'card trackcard2' + (x.available ? '' : ' off')} key=${x.id}
            disabled=${!x.available} aria-disabled=${!x.available}
            onClick=${() => { if (x.available) { setPackId(x.id); setTrack(null); setIntake({}); } }}>
          <${Icon} k=${x.tracks[0].icon} />
          <div class="tkbody">
            <div class="tkname">${x.name}
              ${x.recommended && rec.track ? html`<span class="rectag" key="r">추천</span>` : null}</div>
            <div class="tkdesc">${x.tagline}</div>
            <div class="tkmeta">${x.weeksTotal}주 · ${x.phases.length}단계${x.tracks.length > 1 ? ` · 방식 ${x.tracks.length}가지` : ''}</div>
            ${x.available ? null : html`<div class="tkmeta" key="g">${GATE_TEXT[x.reason] || '지금은 시작할 수 없어요'}</div>`}
          </div>
          <span class="muted">›</span>
        </button>`)}
        ${skip}
        <div class="bottompad"></div>
      </div>
    </div>`;
  }

  // ② 트랙(방식) 고르기
  if (!tr) {
    const recTrack = pk.recommended ? (str(rec.track) || pk.tracks[0].id) : '';
    return html`<div key="trackpick">
      <${Header} title=${single ? '루틴 시작' : pk.name} onBack=${single ? null : back} />
      <div class="scroll">
        ${single ? diag : null}
        <div class="sectitle" key="t1" style="margin-top:14px">어떤 기록부터 시작할까요?</div>
        <p class="muted" style="font-size:12.5px;margin-bottom:10px">
          ${pk.weeksTotal}주 동안 하루 한 가지. 언제든 바꿀 수 있어요.</p>
        ${pk.tracks.map((t) => html`<button class="card trackcard2" key=${t.id}
            onClick=${() => { setTrack(t.id); setIntake({}); }}>
          <${Icon} k=${t.icon} />
          <div class="tkbody">
            <div class="tkname">${t.name}
              ${t.id === recTrack ? html`<span class="rectag" key="r">추천</span>` : null}</div>
            <div class="tkdesc">${t.desc}</div>
          </div>
          <span class="muted">›</span>
        </button>`)}
        ${single ? skip : null}
        <div class="bottompad"></div>
      </div>
    </div>`;
  }

  // ③ 문진 → 시작
  const canBack = !single || pk.tracks.length > 1;
  return html`<div key="intake">
    <${Header} title=${tr.name} onBack=${canBack ? back : null} />
    <div class="scroll">
      <p class="muted" style="line-height:1.7">몇 가지만 알려주시면 ${pk.weeksTotal}주 루틴을 만들어 드려요.</p>
      ${pk.firstWeek && pk.firstWeek.mission ? html`<div class="card" key="fw" style="margin:10px 0">
        <div class="sectitle">첫 주</div>
        <div style="font-size:14px">${pk.firstWeek.theme}</div>
        <div class="muted" style="font-size:12.5px;margin-top:4px">${pk.firstWeek.mission}</div>
      </div>` : html`<div style="height:10px" key="sp"></div>`}
      ${qs.length ? qs.map((q) => html`<div class="card" key=${q.id} style="margin-bottom:10px">
        <div style=${`font-size:14px;margin-bottom:${q.why ? 2 : 8}px`}>${q.q}</div>
        ${q.why ? html`<div class="muted" key="why" style="font-size:12px;margin-bottom:8px">${q.why}</div>` : null}
        <div class="chips">
          ${q.options.map((o) => html`<button class=${'chip' + (intake[q.id] === o.value ? ' sel' : '')}
            key=${o.value} aria-pressed=${intake[q.id] === o.value}
            onClick=${() => setIntake((x) => ({ ...x, [q.id]: o.value }))}>${o.label}</button>`)}
        </div>
      </div>`) : html`<div class="muted" key="noq" style="font-size:13px">바로 시작할 수 있어요.</div>`}
      ${err ? html`<div class="err" key="serr">${err}</div>` : null}
      <button class="btn" key="go" style="margin-top:8px"
        disabled=${busy || !ready} onClick=${start}>
        ${busy ? '만드는 중…' : `${pk.weeksTotal}주 루틴 시작하기`}</button>
      <div class="bottompad"></div>
    </div>
  </div>`;
}
