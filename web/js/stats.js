// stats.js — 화면 2 '오늘의 기록'. 정본: docs/design/todays-me-mockups/spec-02-daily-stats.md.
// 규칙: 링 중앙은 점수가 아니라 완료 트랙 수. 지표 0·미측정은 회색 '–'. 환산·하이라이트·연속 문구는
//       서버 문자열을 그대로 렌더한다(FR-T2-03). 남과 비교·퍼센트·빈 컵 그리드 금지.

import { GET, errText } from './api.js';
import { html, Header, Loading, ErrorView, useLoader, arr, num, str } from './ui.js';
import { elementSvg, ICON } from './archetypes.js';

const ARC = { water: '#4C86F0', activity: '#FF8A5B', mind: '#8E7BEF' };

function Ring({ tracks, count }) {
  const on = (k) => (tracks && tracks[k] === 'done');
  return html`<div class="fl-ringwrap" key="ring">
    <svg width="176" height="176" viewBox="0 0 176 176" aria-hidden="true">
      <circle cx="88" cy="88" r="70" fill="none" stroke="#EFE6D6" stroke-width="22"/>
      <path d="M88 18 A70 70 0 0 1 153.8 112" fill="none" stroke=${on('diet') ? ARC.water : '#EFE6D6'} stroke-width="22" stroke-linecap="round" class="fl-arc"/>
      <path d="M141.7 141.7 A70 70 0 0 1 43 145.6" fill="none" stroke=${on('exercise') ? ARC.activity : '#EFE6D6'} stroke-width="22" stroke-linecap="round" class="fl-arc"/>
      <path d="M27.4 123 A70 70 0 0 1 75.8 19.1" fill="none" stroke=${on('habit') ? ARC.mind : '#EFE6D6'} stroke-width="22" stroke-linecap="round" class="fl-arc"/>
      <circle cx="146" cy="52" r="15" fill="#FFF8EC"/><circle cx="88" cy="158" r="15" fill="#FFF8EC"/><circle cx="30" cy="52" r="15" fill="#FFF8EC"/>
    </svg>
    <span class="fl-ringel fl-ringel-w" dangerouslySetInnerHTML=${{ __html: elementSvg('water', on('diet') ? 'awake' : 'plain', 16) }}></span>
    <span class="fl-ringel fl-ringel-b" dangerouslySetInnerHTML=${{ __html: elementSvg('bolt', 'plain', 14) }}></span>
    <span class="fl-ringel fl-ringel-m" dangerouslySetInnerHTML=${{ __html: elementSvg('moon', 'plain', 16) }}></span>
    <div class="fl-ringcenter">
      <div class="fl-ringnum lex">${num(count)}</div>
      <div class="fl-ringcap">${num(count) === 3 ? '트랙 모두 완료' : '트랙 완료'}</div>
    </div>
  </div>`;
}

function Metric({ kind, m }) {
  const dash = html`<span class="fl-dash">–</span>`;
  if (kind === 'water_cups') {
    return html`<div class="fl-mcard fl-mcard-water" key="water">
      <div class="fl-mtop">
        <div class="fl-mnum"><span class="lex">${m ? m.value : dash}</span><span class="jua">컵의 물</span></div>
        ${m && m.conversion_text ? html`<span class="fl-conv">${m.conversion_text}</span>` : null}
      </div>
      ${m ? html`<div class="fl-cups">
        ${Array.from({ length: Math.min(8, num(m.value)) }).map((_, i) => html`<span key=${i}
          dangerouslySetInnerHTML=${{ __html: ICON.cup('#4C86F0', 32) }}></span>`)}
      </div>` : html`<div class="fl-mcap">아직 기록이 없어요</div>`}
    </div>`;
  }
  if (kind === 'steps') {
    return html`<div class="fl-mcard fl-mcard-steps" key="steps">
      <span class="fl-mchar" dangerouslySetInnerHTML=${{ __html: elementSvg('bolt', 'awake', 46) }}></span>
      <div class="fl-mlabel jua">걸음</div>
      <div class="fl-mbig lex">${m ? num(m.value).toLocaleString() : dash}</div>
      <div class="fl-mcap">${m ? (m.stale ? '조금 뒤에 들어와요' : (m.conversion_text || '')) : '탭해서 적어요'}</div>
    </div>`;
  }
  return html`<div class="fl-mcard fl-mcard-mind" key="mind">
    <span class="fl-mchar" dangerouslySetInnerHTML=${{ __html: ICON.cloud(64) }}></span>
    <div class="fl-mlabel jua">마음챙김</div>
    <div class="fl-mbig"><span class="lex">${m ? m.value : dash}</span>${m ? html`<span class="jua fl-munit">분</span>` : null}</div>
    <div class="fl-mcap">${m ? (m.conversion_text || '') : '1분이면 충분해요'}</div>
  </div>`;
}

export function StatsView({ go, date }) {
  const q = date ? `?date=${encodeURIComponent(date)}` : '';
  const L = useLoader(() => GET('/metrics/day' + q), [date]);
  const back = () => go('today');

  if (L.state === 'loading') return html`<div key="sl"><${Header} title="오늘의 기록" onBack=${back} /><${Loading} /></div>`;
  if (L.state === 'error') {
    return html`<div key="se"><${Header} title="오늘의 기록" onBack=${back} />
      <${ErrorView} err=${L.err || {}} text=${errText(L.err)} onRetry=${L.reload} /></div>`;
  }
  const d = L.data || {};
  const metrics = arr(d.metrics);
  const byKind = Object.fromEntries(metrics.map((m) => [m.kind, m]));
  const cta = str(d.cta, 'go_today');
  const ctaLabel = { reveal: '오늘의 캐릭터 만나기', reveal_replay: '캐릭터 다시 보기',
    go_today: '오늘 하나만 남기러 가기', weekly_report: '이번 주 기록 보기' }[cta] || '돌아가기';
  const onCta = () => {
    if (cta === 'reveal' || cta === 'reveal_replay') go('reveal', { date: d.date });
    else if (cta === 'weekly_report') go('report', {});
    else go('today');
  };

  return html`<div class="fl-screen fl-bg-lavender" key="stats">
    <${Header} title=${d.is_past ? `${str(d.date)} 기록` : '오늘의 기록'} onBack=${back} />
    <div class="scroll fl-scroll">
      <div class="fl-ringcard" key="ringcard">
        <${Ring} tracks=${d.tracks} count=${d.completed_count} />
        <div class="fl-ringside">
          <div class="jua fl-ringtitle">${num(d.completed_count) === 3 ? html`오늘은<br/>꽉 찬 하루` : num(d.completed_count) > 0 ? html`오늘도<br/>남겼어요` : html`오늘의<br/>기록`}</div>
          <div class="fl-ringsub">${str(d.streak_text)}</div>
        </div>
      </div>

      <${Metric} kind="water_cups" m=${byKind.water_cups || null} />
      <div class="fl-mrow">
        <${Metric} kind="steps" m=${byKind.steps || null} />
        <${Metric} kind="mindful_min" m=${byKind.mindful_min || null} />
      </div>

      ${d.highlight && d.highlight.text ? html`<div class="fl-highlight" key="hl">
        <span class="fl-hlstar" dangerouslySetInnerHTML=${{ __html: ICON.star('#141414', 18) }}></span>
        <span>${d.highlight.text}</span>
      </div>` : null}

      <button class="fl-cta fl-cta-sticky" key="cta" onClick=${onCta}>
        <span>${ctaLabel}</span><span dangerouslySetInnerHTML=${{ __html: ICON.arrow() }}></span>
      </button>
      <div class="bottompad"></div>
    </div>
  </div>`;
}
