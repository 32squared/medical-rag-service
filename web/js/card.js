// card.js — 화면 4 '공유 카드'. 정본: spec-04-share-card.md, 02-dev-requirements FR-T4-01~08.
// 규칙: 서버 화이트리스트 페이로드만 렌더. 숫자 숨기기는 페이로드에서 제거(서버). 편집은 800ms 디바운스 자동 저장,
//       00:10 이후 잠금(409). 모든 공유 실패는 이미지 저장으로 수렴. 친구 초대·랭킹 없음.

import { useState, useEffect, useRef } from 'preact/hooks';
import { GET, POST, errText, getJSON } from './api.js';
import { html, Header, Loading, ErrorView, useLoader, arr, str, num } from './ui.js';
import { ICON, ARCHETYPES } from './archetypes.js';
import { renderCard, shareCanvas, THEMES } from './cardRender.js';

const PATCH = (p, body) => getJSON(p, { method: 'PATCH', body: body || {} });
const STICKERS = ['star', 'cloud', 'bolt', 'drop', 'moon'];

function Preview({ payload, archetypeId, format }) {
  const ref = useRef(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const c = await renderCard(payload, archetypeId, format);
        if (!alive || !ref.current) return;
        ref.current.innerHTML = '';
        c.style.width = '100%'; c.style.height = 'auto'; c.style.display = 'block';
        c.style.borderRadius = '28px';
        ref.current.appendChild(c); setErr('');
      } catch (e) { if (alive) setErr('카드를 그리지 못했어요.'); }
    })();
    return () => { alive = false; };
  }, [JSON.stringify(payload), archetypeId, format]);
  return html`<div class=${'fl-cardprev' + (format === 'feed' ? ' fl-cardprev-feed' : '')} key="prev">
    <div ref=${ref} class="fl-cardcanvas"></div>
    ${err ? html`<div class="fl-note">${err}</div>` : null}
  </div>`;
}

export function CardView({ go, date }) {
  const L = useLoader(() => POST('/card', { date: date || undefined }), [date]);
  const [format, setFormat] = useState('story');
  const [local, setLocal] = useState(null);       // 로컬 편집본 {theme_id, stickers, comment, hide_numbers}
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const deb = useRef(null);
  const back = () => go('reveal', { date });

  if (L.state === 'loading') return html`<div key="cl"><${Header} title="공유 카드" onBack=${back} /><${Loading} /></div>`;
  if (L.state === 'error') {
    const e = L.err || {};
    const detail = e.data && e.data.detail;
    const text = detail === 'no_archetype' ? '오늘의 캐릭터가 아직 없어요.' : detail === 'band_gate' ? '지금은 기록만 남겨둘게요.' : errText(e);
    return html`<div key="ce"><${Header} title="공유 카드" onBack=${back} />
      <${ErrorView} err=${e} text=${text} onRetry=${L.reload} /></div>`;
  }

  const card = L.data || {};
  const p0 = card.payload || {};
  const p = { ...p0, ...(local || {}) };
  if (local && local.hide_numbers) { p.metrics = []; p.rarity_pct = null; }
  const locked = !!card.locked;
  const archetypeId = Object.keys(ARCHETYPES).find((k) => ARCHETYPES[k].nameEn === p.archetype_en) || 'balance_monk';

  function edit(patch) {
    if (locked) { setNote('이 카드는 더 이상 고칠 수 없어요.'); return; }
    const next = { theme_id: p.theme_id, stickers: arr(p.stickers), comment: p.comment || '', hide_numbers: !!p.hide_numbers, ...(local || {}), ...patch };
    setLocal(next);
    if (deb.current) clearTimeout(deb.current);
    deb.current = setTimeout(async () => {
      const r = await PATCH(`/card/${card.card_id}`, next);
      if (!r.ok) setNote(errText(r) || '저장하지 못했어요.'); else setNote('');
    }, 800);
  }

  function addSticker(type) {
    const st = arr(p.stickers);
    if (st.length >= 6 || st.filter((s) => s.type === type).length >= 3) { setNote('스티커는 6개, 종류별 3개까지예요.'); return; }
    const spots = [[.18, .18], [.82, .22], [.7, .5], [.25, .62], [.85, .7], [.5, .12]];
    const [x, y] = spots[st.length % spots.length];
    edit({ stickers: [...st, { type, x, y, scale: 1, rot: 0 }] });
  }
  function clearStickers() { edit({ stickers: [] }); }

  async function share(kind) {
    setBusy(true); setNote('');
    try {
      const c = await renderCard(p, archetypeId, kind === 'kakao' ? 'feed' : format);
      const res = await shareCanvas(c, `todays-me-${str(card.date)}.png`);
      setNote(res === 'shared' ? '공유했어요' : res === 'downloaded' ? '사진에 저장했어요' : res === 'cancelled' ? '' : '지금은 보내지 못했어요. 이미지로 저장해 주세요.');
    } catch { setNote('카드를 그리지 못했어요.'); }
    setBusy(false);
  }

  return html`<div class="fl-screen fl-bg-mint" key="card">
    <${Header} title="공유 카드" onBack=${back} />
    <div class="scroll fl-scroll">
      <div class="fl-chiprow" key="fmt">
        <button class=${'fl-chip' + (format === 'story' ? ' on' : '')} onClick=${() => setFormat('story')}>9:16 스토리</button>
        <button class=${'fl-chip' + (format === 'feed' ? ' on' : '')} onClick=${() => setFormat('feed')}>1:1 피드</button>
        <span style="flex:1"></span>
        <button class="fl-chip fl-chip-toggle" aria-pressed=${!!p.hide_numbers} onClick=${() => edit({ hide_numbers: !p.hide_numbers })}>
          숫자 숨기기<i class=${'fl-sw' + (p.hide_numbers ? ' on' : '')}></i></button>
      </div>

      <${Preview} payload=${p} archetypeId=${archetypeId} format=${format} />

      <div class="fl-chiprow" key="theme">
        <span class="fl-rowlabel">테마</span>
        ${Object.keys(THEMES).map((t) => html`<button class=${'fl-swatch' + (p.theme_id === t ? ' on' : '')} key=${t}
          style=${`background:${THEMES[t].bg}`} aria-label=${t} aria-pressed=${p.theme_id === t} onClick=${() => edit({ theme_id: t })}></button>`)}
      </div>
      <div class="fl-chiprow" key="stk">
        <span class="fl-rowlabel">스티커</span>
        ${STICKERS.map((t) => html`<button class="fl-stkbtn" key=${t} aria-label=${t} onClick=${() => addSticker(t)}
          dangerouslySetInnerHTML=${{ __html: ICON.star({ star: '#FFD84D', cloud: '#CDBFF7', bolt: '#FFB800', drop: '#4C86F0', moon: '#8E7BEF' }[t], 20) }}></button>`)}
        ${arr(p.stickers).length ? html`<button class="fl-stkbtn fl-stkclear" onClick=${clearStickers} aria-label="스티커 지우기"
          dangerouslySetInnerHTML=${{ __html: ICON.close('#2F4A3A', 16) }}></button>` : null}
      </div>
      <input class="fl-comment" maxlength="20" placeholder="한 줄 코멘트 (20자)" value=${p.comment || ''}
        disabled=${locked} onInput=${(e) => edit({ comment: e.target.value.slice(0, 20) })} />

      ${note ? html`<div class="fl-note" key="note">${note}</div>` : null}
      ${locked ? html`<div class="fl-note" key="lock">이 날의 카드는 잠겼어요. 보기만 할 수 있어요.</div>` : null}

      <button class="fl-cta" disabled=${busy} onClick=${() => share('share')}>
        <span>${busy ? '준비 중…' : '공유하기'}</span><span dangerouslySetInnerHTML=${{ __html: ICON.arrow() }}></span>
      </button>
      <div class="fl-btnrow">
        <button class="fl-btn-white" disabled=${busy} onClick=${() => share('kakao')}>1:1로 공유</button>
        <button class="fl-btn-white" disabled=${busy} onClick=${() => share('save')}>이미지 저장</button>
      </div>
      <div class="bottompad"></div>
    </div>
  </div>`;
}
