// today.js — '오늘' 탭. 앱의 정체성 화면. 정본 §D-4(홈 섹션 우선순위) · §B(커리큘럼).
//
// 전략 근거: 앱을 여는 이유를 "질문이 생겨서" → "오늘 것이 아직 안 끝나서" 로 바꾼다.
// 그래서 화면 최상단(above the fold)은 **오늘의 행동 1개 + 1탭 완료**가 차지한다.

import { useState, useRef } from 'preact/hooks';
import { GET, POST, errText, uuid } from './api.js';
import {
  html, Header, Loading, ErrorView, Empty, useLoader, useLatest, normToday, arr, num,
} from './ui.js';

const WD = ['월', '화', '수', '목', '금', '토', '일'];

// ── 주간 7일 점 ──────────────────────────────────────────────────
function WeekDots({ days }) {
  const list = arr(days);
  if (!list.length) return null;
  return html`<div class="weekdots" key="weekdots">
    ${list.map((d) => html`<div class=${'wd wd-' + d.state} key=${d.date || d.weekday}>
      <span class="wdlabel">${d.weekday}</span>
      <span class="wddot" aria-hidden="true"></span>
    </div>`)}
  </div>`;
}

// ── 12주 진도 바(순수 CSS) ───────────────────────────────────────
function ProgramStrip({ weeks, current, onOpen }) {
  const list = arr(weeks);
  if (!list.length) return null;
  return html`<button class="strip" key="strip" onClick=${onOpen} aria-label="12주 프로그램 보기">
    <div class="striprow">
      ${list.map((w) => html`<span
        class=${'wseg wseg-' + w.state + (w.w === current ? ' wseg-now' : '')}
        key=${'w' + w.w} title=${`${w.w}주 ${w.done}/${w.goal}일`}></span>`)}
    </div>
    <div class="stripfoot">
      <span>${current}주차 / 12주</span><span class="stripmore">전체 보기 ›</span>
    </div>
  </button>`;
}

// ── 오늘의 행동 카드(히어로) ─────────────────────────────────────
function TodayCard({ t, busy, onDone, onChoice, onSkip, onNA }) {
  if (!t) return null;
  const done = t.status === 'done';
  const opts = arr(t.input.options);
  const isChoice = t.input.kind === 'choice' && opts.length > 0;

  return html`<div class=${'hero' + (done ? ' hero-done' : '')} key="hero">
    <div class="herotop">
      <span class="herotag">${done ? '오늘 완료' : '오늘의 행동'}</span>
      ${t.minutes ? html`<span class="heromin">${t.minutes}분</span>` : null}
    </div>
    <div class="herotext">${t.text}</div>
    ${t.cite ? html`<div class="herocite">근거 · ${t.cite}</div>` : null}

    ${done ? html`<div class="heroDoneRow" key="donerow">
        <span class="okmark" aria-hidden="true">✓</span>
        <span>${t.value ? `기록됨 · ${t.value}` : '오늘 기록을 남겼어요'}</span>
      </div>`
    : isChoice ? html`<div class="heroopts" key="opts">
        ${opts.map((o) => html`<button class="optbtn" key=${o} disabled=${busy}
          onClick=${() => onChoice(o)}>${o}</button>`)}
      </div>`
    : html`<button class="btn herobtn" key="tapbtn" disabled=${busy}
        onClick=${onDone}>${busy ? '기록 중…' : '오늘 완료하기'}</button>`}

    ${done ? null : html`<div class="herosub" key="sub">
      <button class="linkbtn" disabled=${busy} onClick=${onSkip}>오늘은 패스</button>
      <span class="dotsep">·</span>
      <button class="linkbtn" disabled=${busy} onClick=${onNA}>해당없음</button>
    </div>`}
  </div>`;
}

export function TodayTab({ go, onAsk, onStart }) {
  const L = useLoader(() => GET('/routine/today'), []);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [justDone, setJustDone] = useState(false);
  const sending = useRef(false);           // stale closure 에 안전한 중복 전송 가드
  const race = useLatest();

  if (L.state === 'loading') {
    return html`<${Loading} />`;
  }
  if (L.state === 'error') {
    const e = L.err || {};
    return html`<div key="err">
      <${Header} title="오늘" />
      <${ErrorView} err=${e} text=${errText(e)} onRetry=${L.reload} />
    </div>`;
  }

  const d = normToday(L.data);

  // ── 응급: 루틴 전면 중단 ──
  if (d.safety) {
    return html`<div key="safety">
      <${Header} title="지금 확인하세요" />
      <div class="pad">
        <div class="safetybox">
          <div class="safetytitle">🚨 ${d.safety.text}</div>
          <div class="muted" style="margin-top:8px;font-size:13px">
            안전이 우선이에요. 루틴은 잠시 멈춰둘게요.</div>
        </div>
        <button class="btn" style="margin-top:14px" onClick=${() => go('finder')}>가까운 병원·약국 찾기</button>
      </div>
    </div>`;
  }

  // ── 프로그램 없음: 시작 유도 ──
  if (!d.program) {
    return html`<div key="noprog">
      <${Header} title="오늘" />
      <div class="pad">
        ${d.band ? html`<div class="bandchip" key="band">현재 ${d.band} 구간</div>` : null}
        <${Empty}
          title="3개월 루틴을 시작해볼까요?"
          desc=${'하루 30초, 오늘의 행동 1개부터 시작합니다. 12주 동안 기록이 쌓이면 내 패턴이 보이고, 진료·검진에서도 쓸 수 있어요.'}
          cta="루틴 시작하기" onCta=${onStart} />
        ${d.today ? html`<div class="previewcard" key="preview">
          <div class="previewlabel">이런 행동부터 시작해요</div>
          <div class="previewtext">${d.today.text}</div>
        </div>` : null}
      </div>
    </div>`;
  }

  // ── 체크인 ──
  async function send(status, value) {
    if (sending.current) return;
    sending.current = true;
    setBusy(true); setMsg('');
    const id = race.begin();
    try {
      const r = await POST('/routine/checkin', {
        program_id: d.program.id, action_id: d.today ? d.today.id : '',
        slot: 'main', status, value: value || null,
        idempotency_key: uuid(),
        client_ts: new Date().toISOString(),
      });
      if (!race.accept(id)) return;
      if (!r.ok) { setMsg(errText(r)); return; }
      const body = r.data || {};
      if (body.accepted === false) { setMsg(String(body.message || '기록하지 못했어요.')); return; }
      if (status === 'done') {
        setJustDone(true);
        setTimeout(() => { if (race.alive()) setJustDone(false); }, 1400);
      }
      await L.reload();
    } catch {
      if (race.accept(id)) setMsg('기록하지 못했어요. 잠시 후 다시 시도해 주세요.');
    } finally {
      sending.current = false;
      if (race.alive()) setBusy(false);
    }
  }

  const p = d.program;
  const w = d.week;
  const stats = d.stats;

  return html`<div key="today">
    <${Header} title=${`${p.week}주차 · ${p.phase}`}
      right=${html`<span class="streakchip" key="streak">🔥 ${num(stats.streak)}</span>`} />
    <div class="scroll">
      ${d.banner ? html`<div class="banner" key="banner">${d.banner}</div>` : null}

      ${d.reportDue ? html`<button class="reportcue" key="report"
        onClick=${() => go('report', { week: d.reportDue.week })}>
        📊 ${d.reportDue.week}주차 리포트가 준비됐어요<span class="stripmore">보기 ›</span>
      </button>` : null}

      <${TodayCard} t=${d.today} busy=${busy}
        onDone=${() => send('done')}
        onChoice=${(v) => send('done', v)}
        onSkip=${() => send('skip')}
        onNA=${() => send('na')} />

      ${justDone ? html`<div class="toast" key="toast">기록했어요 · 🔥 ${num(stats.streak)}일째</div>` : null}
      ${msg ? html`<div class="err" key="msg">${msg}</div>` : null}

      ${d.evidence ? html`<div class="evidence" key="evidence">
        <span class="evlabel">내 상태 기준</span> ${d.evidence.label}
      </div>` : null}

      <div class="themecard" key="theme">
        <div class="themetitle">${p.theme}</div>
        ${p.mission ? html`<div class="thememission">이번 주 미션 · ${p.mission}</div>` : null}
        ${w ? html`<div class="themeprog">
          <div class="pbar"><div class="pfill" style=${`width:${Math.min(100, Math.round(w.done / Math.max(1, w.goal) * 100))}%`}></div></div>
          <div class="pnum">${w.done}/${w.goal}일</div>
        </div>` : null}
      </div>

      <${WeekDots} days=${d.weekDays} />

      ${d.support.length ? html`<div class="supportwrap" key="support">
        <div class="sectitle">함께 하면 좋은 것</div>
        ${d.support.map((s) => html`<div class="suprow" key=${s.key || s.text}>
          <div class="supmain"><div>${s.text}</div>
            ${s.cite ? html`<div class="supcite">근거 · ${s.cite}</div>` : null}</div>
          <span class=${'supstate' + (s.status === 'done' ? ' on' : '')}>${s.status === 'done' ? '✓' : ''}</span>
        </div>`)}
      </div>` : null}

      ${d.coach && d.coach.message ? html`<div class="coach" key="coach">${d.coach.message}</div>` : null}

      <${ProgramStrip} weeks=${d.weeks} current=${p.week} onOpen=${() => go('program')} />

      ${d.chips.length ? html`<div class="askwrap" key="ask">
        <div class="sectitle">이번 주 궁금한 것</div>
        <div class="chips">
          ${d.chips.map((q) => html`<button class="chip" key=${q} onClick=${() => onAsk(q)}>${q}</button>`)}
        </div>
      </div>` : null}

      <div class="bottompad"></div>
    </div>
  </div>`;
}
