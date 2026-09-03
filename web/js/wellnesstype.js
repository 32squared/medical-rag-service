// wellnesstype.js — 웰니스 타입 5종(성향 층): 온보딩 문진 4문항 · 결과 화면 · 타입 카드 · 설정 변경.
// 정본: 00-concept-brief §4-2·§4-3, 02-dev-requirements FR-C10~15, spec-04 §18.
// 규칙: 타입 간 우열 없음, 언제든 변경 가능, 밴드와 무관. "분석 결과"류 단정 표현 금지. 이모지 없음.

import { useState } from 'preact/hooks';
import { GET, POST, PUT, errText } from './api.js';
import { html, Header, Loading, ErrorView, useLoader, arr, str } from './ui.js';
import { WELLNESS_TYPES, ICON } from './archetypes.js';

// ── 문진 ────────────────────────────────────────────────────────
export function TypeQuiz({ onDone, onSkip }) {
  const L = useLoader(() => GET('/wellness-type/quiz'), []);
  const [answers, setAnswers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  if (L.state === 'loading') return html`<div key="ql"><${Header} title="내 웰니스 타입" /><${Loading} /></div>`;
  if (L.state === 'error') {
    return html`<div key="qe"><${Header} title="내 웰니스 타입" />
      <${ErrorView} err=${L.err} text=${errText(L.err)} onRetry=${L.reload} />
      <div class="pad"><button class="btn ghost" onClick=${onSkip}>나중에 하기</button></div></div>`;
  }
  const qs = arr((L.data || {}).questions);
  const i = answers.length;
  const q = qs[i];

  async function pick(idx) {
    const next = [...answers, idx];
    if (next.length < qs.length) { setAnswers(next); return; }
    setBusy(true); setErr('');
    const r = await POST('/wellness-type/quiz', { answers: next });
    setBusy(false);
    if (!r.ok) { setErr(errText(r)); setAnswers([]); return; }
    onDone(r.data);
  }

  if (!q) return html`<div key="qz"><${Header} title="내 웰니스 타입" /><${Loading} /></div>`;
  return html`<div class="fl-screen fl-bg-lavender" key="quiz">
    <${Header} title="내 웰니스 타입" onBack=${i > 0 ? () => setAnswers(answers.slice(0, -1)) : null} />
    <div class="scroll fl-scroll">
      <div class="fl-quizstep">${i + 1} / ${qs.length}</div>
      <div class="fl-headline jua" style="font-size:30px">${str(q.text)}</div>
      <div class="fl-quizopts">
        ${arr(q.options).map((o) => html`<button class="fl-quizopt" key=${o.index} disabled=${busy} onClick=${() => pick(o.index)}>${str(o.label)}</button>`)}
      </div>
      ${err ? html`<div class="err">${err}</div>` : null}
      <button class="fl-textbtn" onClick=${onSkip}>나중에 하기</button>
      <div class="bottompad"></div>
    </div>
  </div>`;
}

// ── 결과 화면 ──────────────────────────────────────────────────
export function TypeResult({ type, onDone, onCard }) {
  const t = WELLNESS_TYPES[type && type.type_id] || null;
  if (!t) return html`<div key="tr0"><${Header} title="내 웰니스 타입" /><div class="pad"><button class="btn" onClick=${onDone}>시작하기</button></div></div>`;
  return html`<div class="fl-screen" style=${`background:${t.bg}`} key="typeresult">
    <div class="fl-revealhead" style="padding:14px var(--page-x) 0">
      <span class="fl-pill fl-pill-white"><span dangerouslySetInnerHTML=${{ __html: ICON.star('#141414', 14) }}></span>내 웰니스 타입</span>
      <button class="fl-icobtn fl-icobtn-white" aria-label="닫기" onClick=${onDone} dangerouslySetInnerHTML=${{ __html: ICON.close() }}></button>
    </div>
    <div class="scroll fl-scroll">
      <div class="fl-typestage">
        <div class="fl-stagecard fl-stagecard-back" style="background:var(--c-cream)"></div>
        <div class="fl-typeimg"><img src=${t.img} alt=${`${t.nameKo} 캐릭터`} /></div>
      </div>
      <div class="fl-revealbody">
        <div style="font-size:13px;color:rgba(20,20,20,.7)">문진 결과, 당신은</div>
        <div class="fl-revealko jua" style="font-size:34px">${t.nameKo}</div>
        <div class="lex" style="font-size:13px;font-weight:700;letter-spacing:.12em;color:rgba(20,20,20,.7)">${t.nameEn}</div>
        <div style="font-size:14px;margin-top:6px">${str(type.one_liner)}</div>
        <div class="fl-tags">${t.traits.map((x) => html`<span class="fl-tag" key=${x}>${x}</span>`)}</div>
        <div style="font-size:12px;color:rgba(20,20,20,.7);margin-top:4px">타입은 설정에서 언제든 바꿀 수 있어요</div>
      </div>
      <div class="fl-revealactions">
        ${onCard ? html`<button class="fl-cta" onClick=${onCard}><span>타입 카드 만들기</span><span dangerouslySetInnerHTML=${{ __html: ICON.arrow() }}></span></button>` : null}
        <button class="fl-textbtn" onClick=${onDone}>바로 시작하기</button>
      </div>
    </div>
  </div>`;
}

// ── 온보딩 단계 래퍼: 문진 → 결과 ──────────────────────────────
export function TypeOnboarding({ onDone }) {
  const [res, setRes] = useState(null);
  if (!res) return html`<${TypeQuiz} onDone=${setRes} onSkip=${onDone} />`;
  return html`<${TypeResult} type=${res} onDone=${onDone} />`;
}

// ── 설정: 내 웰니스 타입 변경 ──────────────────────────────────
export function TypeSettings({ go }) {
  const L = useLoader(() => GET('/wellness-type'), []);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const back = () => go('settings');
  if (L.state === 'loading') return html`<div key="tl"><${Header} title="내 웰니스 타입" onBack=${back} /><${Loading} /></div>`;
  if (L.state === 'error') return html`<div key="te"><${Header} title="내 웰니스 타입" onBack=${back} /><${ErrorView} err=${L.err} text=${errText(L.err)} onRetry=${L.reload} /></div>`;
  const cur = (L.data || {}).type_id || null;
  async function choose(id) {
    setBusy(id); setNote('');
    const r = await PUT('/wellness-type', { type_id: id });
    setBusy('');
    if (!r.ok) { setNote(errText(r)); return; }
    L.reload();
  }
  return html`<div class="fl-screen fl-bg-lemon" key="typesettings">
    <${Header} title="내 웰니스 타입" onBack=${back} />
    <div class="scroll fl-scroll">
      <div class="fl-subline">우열은 없어요. 지금의 나에 가까운 걸 고르면 돼요.</div>
      ${Object.keys(WELLNESS_TYPES).map((id) => { const t = WELLNESS_TYPES[id]; return html`<button class=${'fl-typerow' + (cur === id ? ' on' : '')} key=${id}
        disabled=${busy === id} onClick=${() => choose(id)} style=${`background:${t.bg}`}>
        <img class="fl-typethumb" src=${t.img} alt="" />
        <span class="fl-typename"><b class="jua">${t.nameKo}</b><small>${t.traits.join(' · ')}</small></span>
        ${cur === id ? html`<span class="fl-typecheck" dangerouslySetInnerHTML=${{ __html: ICON.check('#FFFFFF', 14) }}></span>` : null}
      </button>`; })}
      ${note ? html`<div class="fl-note">${note}</div>` : null}
      <div class="bottompad"></div>
    </div>
  </div>`;
}
