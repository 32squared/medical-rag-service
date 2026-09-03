// program.js — '프로그램'(12주 진도) 탭 + 주간 리포트. 정본 §D-3 · §B-6.

import { GET, POST, errText } from './api.js';
import {
  html, Header, Loading, ErrorView, Empty, useLoader, normToday, arr, num, str, clamp,
} from './ui.js';

// ── 12주 타임라인 ────────────────────────────────────────────────
function Timeline({ weeks, current, preview }) {
  const list = arr(weeks).length ? arr(weeks) : arr(preview).map((p) => ({
    w: num(p.w, 1), state: 'future', done: 0, goal: num(p.goal_days, 5), theme: str(p.theme),
  }));
  if (!list.length) return null;
  const PHASE = (w) => (w <= 2 ? '정착기' : w <= 6 ? '확장기' : w <= 10 ? '내재화기' : '전환기');
  return html`<div class="timeline" key="timeline">
    ${list.map((w) => html`<div class=${'tlrow tl-' + w.state + (w.w === current ? ' tl-now' : '')}
        key=${'tl' + w.w}>
      <div class="tlweek"><b>${w.w}</b><span>주</span></div>
      <div class="tlbody">
        <div class="tlphase">${PHASE(w.w)}</div>
        <div class="tltheme">${str(w.theme) || '—'}</div>
      </div>
      <div class="tlstat">${w.state === 'future' ? '' : `${num(w.done)}/${num(w.goal, 1)}`}</div>
    </div>`)}
  </div>`;
}

// ── 실천 히트맵(순수 CSS) ────────────────────────────────────────
function Heatmap({ days }) {
  const list = arr(days);
  if (!list.length) return null;
  return html`<div class="heatwrap" key="heat">
    <div class="sectitle">실천 기록</div>
    <div class="heat">
      ${list.map((d) => html`<span class=${'hcell h' + clamp(d.level, 0, 2)}
        key=${d.date} title=${d.date}></span>`)}
    </div>
    <div class="heatlegend"><span class="hcell h0"></span> 없음
      <span class="hcell h1"></span> 부분 <span class="hcell h2"></span> 완료</div>
  </div>`;
}

export function ProgramTab({ go }) {
  const L = useLoader(() => GET('/routine/today'), []);

  if (L.state === 'loading') return html`<${Loading} />`;
  if (L.state === 'error') {
    return html`<div key="perr"><${Header} title="프로그램" />
      <${ErrorView} err=${L.err} text=${errText(L.err)} onRetry=${L.reload} /></div>`;
  }
  const d = normToday(L.data);

  if (!d.program) {
    return html`<div key="pnone"><${Header} title="프로그램" />
      <${Empty} title="아직 시작한 루틴이 없어요"
        desc="3개월 루틴을 시작하면 여기에서 12주 진도를 볼 수 있어요."
        cta="오늘 탭으로 가기" onCta=${() => go('today')} />
    </div>`;
  }

  const p = d.program;
  const st = d.stats;
  return html`<div key="program">
    <${Header} title="12주 프로그램" />
    <div class="scroll">
      <div class="pgsummary" key="sum">
        <div class="pgring">
          <div class="pgweek">${p.week}<span>주</span></div>
          <div class="pgtotal">/ 12주</div>
        </div>
        <div class="pgstats">
          <div><b>${num(st.streak)}</b><span>연속</span></div>
          <div><b>✓ ${num(st.done)}</b><span>총 실천</span></div>
          <div><b>${num(st.adherence)}%</b><span>실천율</span></div>
        </div>
      </div>

      <button class="btn ghost" key="reportbtn" style="margin:4px 0 12px"
        onClick=${() => go('report', {})}>주간 리포트 보기</button>

      <${Timeline} weeks=${d.weeks} current=${p.week} preview=${d.previewWeeks} />
      <${Heatmap} days=${d.days} />
      <div class="bottompad"></div>
    </div>
  </div>`;
}

// ── 주간 리포트 ──────────────────────────────────────────────────
export function ReportView({ week, go, onAsk }) {
  const q = week ? `?week=${encodeURIComponent(week)}` : '';
  const L = useLoader(() => GET('/routine/week-report' + q), [week]);

  if (L.state === 'loading') {
    return html`<div key="rl"><${Header} title="주간 리포트" onBack=${() => go('program')} />
      <${Loading} /></div>`;
  }
  if (L.state === 'error') {
    return html`<div key="re"><${Header} title="주간 리포트" onBack=${() => go('program')} />
      <${ErrorView} err=${L.err} text=${errText(L.err)} onRetry=${L.reload} /></div>`;
  }

  const r = L.data || {};
  const wk = clamp(r.week_no, 1, 12);
  const done = num(r.done_days);
  const goal = num(r.goal_days, 1);
  const bars = arr(r.weekly_bars);
  const nxt = r.next && typeof r.next === 'object' ? r.next : null;
  const questions = arr(r.questions).filter((x) => typeof x === 'string');

  // 열람 처리(확인률 지표) — 실패해도 화면에 영향 없음
  POST('/routine/report/read', { week: wk }).catch(() => {});

  return html`<div key="report">
    <${Header} title=${`${wk}주차 리포트`} onBack=${() => go('program')} />
    <div class="scroll">
      ${r.banner ? html`<div class="banner" key="rb">${r.banner}</div>` : null}

      <div class="rpcard" key="rp1">
        <div class="rpbig">${done}<span>/${goal}일</span></div>
        <div class="rptheme">${str(r.theme)}</div>
        <div class="rprow">
          <span>실천율 <b>${num(r.adherence)}%</b></span>
          <span>연속 <b>${num(r.streak_end)}일</b></span>
          ${num(r.na_days) ? html`<span>해당없음 <b>${num(r.na_days)}일</b></span>` : null}
        </div>
        ${r.delta ? html`<div class="rpdelta">${str(r.delta)}</div>` : null}
      </div>

      ${bars.length ? html`<div class="rpcard" key="rp2">
        <div class="sectitle">주차별 흐름</div>
        <div class="barwrap">
          ${bars.map((b) => html`<div class="barcol" key=${'b' + num(b.w)}>
            <div class="bartrack"><div class="barfill"
              style=${`height:${Math.round(Math.max(0, Math.min(1, Number(b.ratio) || 0)) * 100)}%`}></div></div>
            <span class="barlab">${num(b.w)}</span>
          </div>`)}
        </div>
        ${r.trend_label ? html`<div class="trendlab">패턴 · ${str(r.trend_label)}</div>` : null}
      </div>` : null}

      ${nxt ? html`<div class="rpcard next" key="rp3">
        <div class="sectitle">다음 주 예고</div>
        <div class="nexttheme">${num(nxt.week_no)}주차 · ${str(nxt.theme)}</div>
        ${nxt.mission ? html`<div class="muted" style="font-size:12.5px;margin-top:6px;line-height:1.6">${str(nxt.mission)}</div>` : null}
      </div>` : null}

      ${questions.length ? html`<div class="rpcard" key="rp4">
        <div class="sectitle">이번 주 궁금했던 것</div>
        <div class="chips">
          ${questions.map((qq) => html`<button class="chip" key=${qq} onClick=${() => onAsk(qq)}>${qq}</button>`)}
        </div>
      </div>` : null}

      <div class="bottompad"></div>
    </div>
  </div>`;
}
