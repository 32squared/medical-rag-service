// reveal.js — 화면 3 '오늘의 캐릭터' 리빌. 정본: docs/design/todays-me-mockups/spec-03-archetype-reveal.md.
// 규칙: 사용자가 화면 2 CTA 로만 연다(자동 팝업 금지). 3단계 연출 ≤2.5s, 탭으로 건너뛰기,
//       reduced-motion 이면 페이드만. 같은 날 재진입은 연출 생략. 희귀도 null 이면 줄 자체 숨김.
//       이탈 시 죄책감 문구 없음. 태그는 완료 트랙만.

import { useState, useEffect, useRef } from 'preact/hooks';
import { GET, POST, errText } from './api.js';
import { html, Header, Loading, ErrorView, useLoader, arr, str } from './ui.js';
import { ARCHETYPES, archetypeSvg, slotSvg, ICON } from './archetypes.js';

export const CARD_ENABLED = false;        // Phase 3 에서 true (공유 카드)

function reducedMotion() {
  try { return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
}

export function RevealView({ go, date }) {
  const q = date ? `?date=${encodeURIComponent(date)}` : '';
  const L = useLoader(() => GET('/archetype/day' + q), [date]);
  const [stage, setStage] = useState('idle');      // idle | dim | gather | flip | done
  const timers = useRef([]);
  const back = () => go('stats', { date });

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  useEffect(() => {
    if (L.state !== 'data') return;
    const d = L.data || {};
    if (d.seen_today || reducedMotion()) { setStage('done'); return; }
    setStage('dim');
    const t = (fn, ms) => timers.current.push(setTimeout(fn, ms));
    t(() => setStage('gather'), 400);
    t(() => setStage('flip'), 1400);
    t(() => setStage('done'), 2300);
  }, [L.state]);

  useEffect(() => {
    if (stage !== 'done' || L.state !== 'data') return;
    const d = L.data || {};
    if (!d.seen_today) POST('/archetype/seen', { date: d.date }).catch(() => {});
    try { if (navigator.vibrate) navigator.vibrate(30); } catch { /* noop */ }
  }, [stage, L.state]);

  function skip() {
    if (stage === 'done') return;
    timers.current.forEach(clearTimeout); timers.current = [];
    setStage('done');
  }

  if (L.state === 'loading') return html`<div key="rl"><${Header} title="오늘의 캐릭터" onBack=${back} /><${Loading} /></div>`;
  if (L.state === 'error') {
    const e = L.err || {};
    const detail = e.data && e.data.detail;
    const text = detail === 'no_archetype' ? '오늘은 아직 캐릭터가 없어요. 하나만 남기면 깨어나요.'
      : detail === 'band_gate' ? '지금은 기록만 남겨둘게요.' : errText(e);
    return html`<div key="re"><${Header} title="오늘의 캐릭터" onBack=${back} />
      <${ErrorView} err=${e} text=${text} onRetry=${L.reload} /></div>`;
  }

  const d = L.data || {};
  const a = ARCHETYPES[d.archetype_id] || ARCHETYPES.balance_monk;
  const tags = arr(d.tags);
  const coll = arr(d.collection_last7);

  return html`<div class=${'fl-screen fl-reveal fl-stage-' + stage} key="reveal" style=${`background:${a.bg}`}
    onClick=${skip}>
    <div class="fl-revealhead">
      <span class="fl-pill fl-pill-white"><span dangerouslySetInnerHTML=${{ __html: ICON.star('#141414', 14) }}></span>오늘의 캐릭터</span>
      <button class="fl-icobtn fl-icobtn-white" aria-label="닫기" onClick=${(e) => { e.stopPropagation(); go('today'); }}
        dangerouslySetInnerHTML=${{ __html: ICON.close() }}></button>
    </div>

    <div class="fl-stagewrap" aria-live="polite">
      <div class="fl-stagecard fl-stagecard-back"></div>
      <div class="fl-stagecard fl-stagecard-mid"></div>
      <div class="fl-stagechar" dangerouslySetInnerHTML=${{ __html: archetypeSvg(d.archetype_id, 250) }}></div>
      <div class="fl-gather" aria-hidden="true">
        ${a.elements.map((e) => html`<span class=${'fl-gatherdot fl-gd-' + e} key=${e}></span>`)}
      </div>
      ${stage !== 'done' ? html`<div class="fl-stagehint">${stage === 'dim' ? '오늘의 기록을 모으는 중…' : '탭하면 바로 보여요'}</div>` : null}
    </div>

    <div class="fl-revealbody">
      <div class="fl-revealname lex">${str(d.name_en, a.nameEn)}</div>
      <div class="fl-revealko jua">${str(d.name_ko, a.nameKo)}</div>
      <div class="fl-reveallore">${str(d.lore)}</div>
      ${tags.length ? html`<div class="fl-tags" key="tags">
        ${tags.map((t, i) => html`<span class="fl-tag" key=${t}>
          <i class=${'fl-tagdot fl-tagdot-' + (a.elements[i] || 'water')}></i>${t}</span>`)}
      </div>` : null}
      ${d.rarity_text ? html`<div class="fl-rarity" key="rar">${d.rarity_text}</div>` : null}
      ${coll.length > 1 ? html`<div class="fl-coll" key="coll">
        <span class="fl-colllabel">지난 7일</span>
        ${coll.map((c) => html`<span class=${'fl-slot' + (c.is_today ? ' fl-slot-today' : '')} key=${c.date}
          style=${c.is_today ? '' : `background:${(ARCHETYPES[c.archetype_id] || a).bg}`}
          dangerouslySetInnerHTML=${{ __html: c.is_today ? ICON.star('#FFD84D', 16) : slotSvg(c.archetype_id) }}></span>`)}
      </div>` : html`<div class="fl-colllabel" key="collcap">모으면 여기에 쌓여요</div>`}
    </div>

    <div class="fl-revealactions" onClick=${(e) => e.stopPropagation()}>
      ${CARD_ENABLED ? html`<button class="fl-cta" key="card" onClick=${() => go('card', { date: d.date })}>
        <span>카드 만들기</span><span dangerouslySetInnerHTML=${{ __html: ICON.arrow() }}></span></button>` : null}
      <button class="fl-textbtn" key="done" onClick=${() => go('today')}>오늘은 여기까지</button>
    </div>
  </div>`;
}
