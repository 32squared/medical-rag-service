// cardRender.js — 공유 카드 클라이언트 렌더러(canvas). 정본: spec-04-share-card.md §3·§4-2, 04-integration-plan D3.
//
// 규칙(fail-closed):
//  - 서버 화이트리스트 페이로드만 그린다. 미지 키가 있으면 렌더를 거부한다(조용한 통과 금지).
//  - 카드에 이름·프로필·밴드·검진 수치·연속 끊김·순위를 그리지 않는다 — 페이로드에 애초에 없다.
//  - 포맷: story 1080×1920 / feed 1080×1080. 미리보기는 같은 캔버스를 CSS 로 축소한다.
//  - 폰트는 document.fonts.load 후 그린다. 실패 시 Malgun 폴백 + 숫자 15% 축소.

import { archetypeSvg } from './archetypes.js';

export const CARD_ALLOWED_KEYS = new Set([
  'date_label', 'brand_label', 'metrics', 'archetype_en', 'archetype_ko', 'archetype_lore',
  'rarity_pct', 'theme_id', 'stickers', 'comment', 'hide_numbers', 'wellness_type_label',
]);
const FORBIDDEN = ['bp', 'glucose', 'band', 'grade', 'streak', 'rank', 'percentile', 'missed', 'name', 'profile'];

export const THEMES = {
  coral: { bg: '#E2593A', accent: '#FFD84D', text: '#FFF3E0' },
  lavender: { bg: '#7C6BD9', accent: '#FFD84D', text: '#FFF3E0' },
  forest: { bg: '#4E7A5A', accent: '#FFD84D', text: '#FFF3E0' },
};
const UNIT = { water_cups: '컵의 물', steps: '걸음', mindful_min: '분 마음챙김', active_min: '분 활동' };
const STICKER_COLOR = { star: '#FFD84D', cloud: '#FFFFFF', bolt: '#FFB800', drop: '#4C86F0', moon: '#CDBFF7' };

export function assertPayload(p) {
  if (!p || typeof p !== 'object') throw new Error('card_payload_missing');
  for (const k of Object.keys(p)) {
    if (!CARD_ALLOWED_KEYS.has(k)) throw new Error('card_payload_unknown_key:' + k);
    const lk = k.toLowerCase();
    if (FORBIDDEN.some((f) => lk.includes(f)) && !CARD_ALLOWED_KEYS.has(k)) throw new Error('card_payload_forbidden:' + k);
  }
  if (Array.isArray(p.metrics) && p.metrics.length > 3) throw new Error('card_payload_too_many_metrics');
  if (p.comment && String(p.comment).length > 20) throw new Error('card_payload_comment_too_long');
}

async function ensureFonts() {
  try {
    if (!document.fonts || !document.fonts.load) return false;
    await Promise.all([
      document.fonts.load('800 58px Lexend'), document.fonts.load('700 11px Lexend'),
      document.fonts.load('400 18px Jua'), document.fonts.load('400 13px "Gowun Dodum"'),
    ]);
    return document.fonts.check('800 58px Lexend') && document.fonts.check('400 18px Jua');
  } catch { return false; }
}

function rrect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function star(ctx, cx, cy, r, color) {
  ctx.save(); ctx.translate(cx, cy); ctx.scale(r / 10, r / 10);
  ctx.beginPath(); ctx.moveTo(0, -10); ctx.bezierCurveTo(1, -4, 4, -1, 10, 0); ctx.bezierCurveTo(4, 1, 1, 4, 0, 10);
  ctx.bezierCurveTo(-1, 4, -4, 1, -10, 0); ctx.bezierCurveTo(-4, -1, -1, -4, 0, -10); ctx.closePath();
  ctx.fillStyle = color; ctx.fill(); ctx.restore();
}

function svgImage(svg) {
  return new Promise((resolve) => {
    try {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    } catch { resolve(null); }
  });
}

/** payload + archetype_id + format → HTMLCanvasElement (1080 기준). */
export async function renderCard(payload, archetypeId, format = 'story') {
  assertPayload(payload);
  const fontsOk = await ensureFonts();
  const W = 1080; const H = format === 'feed' ? 1080 : 1920;
  const S = W / 254;                                   // 목업 254px 기준 스케일(4.25)
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const ctx = c.getContext('2d');
  const th = THEMES[payload.theme_id] || THEMES.coral;
  const latin = fontsOk ? 'Lexend' : '"Malgun Gothic", sans-serif';
  const ko = fontsOk ? 'Jua' : '"Malgun Gothic", sans-serif';
  const body = fontsOk ? '"Gowun Dodum"' : '"Malgun Gothic", sans-serif';
  const shrink = fontsOk ? 1 : 0.85;

  // 바탕
  rrect(ctx, 0, 0, W, H, 28 * S); ctx.fillStyle = th.bg; ctx.fill();
  star(ctx, W - 20 * S, 14 * S, 24 * S, th.accent);
  ctx.fillStyle = th.text; ctx.globalAlpha = .9;
  ctx.beginPath(); ctx.arc(190 * S, 150 * S, 4 * S, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
  ctx.fillStyle = th.accent; ctx.beginPath(); ctx.arc(30 * S, (H / S - 190) * S, 3.5 * S, 0, 7); ctx.fill();

  const pad = 20 * S;
  ctx.fillStyle = th.text; ctx.textBaseline = 'top';
  ctx.font = `700 ${11 * S}px ${latin}`;
  drawTracked(ctx, payload.brand_label || "TODAY'S ME", pad, pad, 0.14 * 11 * S);
  ctx.font = `600 ${11 * S}px ${latin}`; ctx.textAlign = 'right';
  ctx.fillText(String(payload.date_label || ''), W - pad, pad); ctx.textAlign = 'left';

  // 지표 3줄
  const metrics = payload.hide_numbers ? [] : (payload.metrics || []).slice(0, 3);
  let y = format === 'feed' ? 70 * S : 110 * S;
  const gap = format === 'feed' ? 52 * S : 74 * S;
  for (const m of metrics) {
    const numText = Number(m.value).toLocaleString();
    ctx.font = `800 ${58 * S * shrink}px ${latin}`;
    ctx.fillText(numText, pad, y);
    const nw = ctx.measureText(numText).width;
    ctx.font = `400 ${18 * S}px ${ko}`;
    ctx.fillText(UNIT[m.kind] || m.unit_label || '', pad + nw + 6 * S, y + (58 * S * shrink - 18 * S) - 4 * S);
    y += gap;
  }
  if (!metrics.length) {
    ctx.font = `400 ${18 * S}px ${ko}`; ctx.fillText('오늘도 남겼어요', pad, y);
  }

  // 캐릭터 + 이름
  const charSize = format === 'feed' ? 120 * S : 84 * S;
  const bottomY = H - pad - 18 * S;
  const img = await svgImage(archetypeSvg(archetypeId, 200));
  if (img) ctx.drawImage(img, W - pad - charSize, bottomY - charSize - 8 * S, charSize, charSize);
  const nameY = bottomY - 20 * S - 2 * 26 * S - 22 * S;
  ctx.fillStyle = th.accent; ctx.font = `800 ${26 * S}px ${latin}`;
  const parts = String(payload.archetype_en || '').split(' ');
  const line1 = parts.slice(0, Math.ceil(parts.length / 2)).join(' ');
  const line2 = parts.slice(Math.ceil(parts.length / 2)).join(' ');
  ctx.fillText(line1, pad, nameY); if (line2) ctx.fillText(line2, pad, nameY + 26 * S);
  ctx.fillStyle = th.text; ctx.font = `400 ${11 * S}px ${body}`;
  const sub = [payload.archetype_ko, payload.rarity_pct == null ? null : `이달 ${payload.rarity_pct}%`].filter(Boolean).join(' · ');
  ctx.fillText(sub, pad, nameY + 26 * S * 2 + 6 * S);
  if (payload.comment) {
    ctx.font = `400 ${13 * S}px ${body}`;
    ctx.fillText(String(payload.comment), pad, nameY - 24 * S);
  }

  // 푸터
  ctx.globalAlpha = .9; ctx.font = `400 ${10.5 * S}px ${ko}`;
  ctx.fillText('오늘의 나', pad, bottomY);
  ctx.font = `400 ${10.5 * S}px ${body}`; ctx.textAlign = 'right';
  ctx.fillText(payload.wellness_type_label || '기록이 남은 하루', W - pad, bottomY); ctx.textAlign = 'left'; ctx.globalAlpha = 1;

  // 스티커
  for (const s of (payload.stickers || []).slice(0, 6)) {
    const x = Number(s.x || 0) * W; const yy = Number(s.y || 0) * H; const sc = Number(s.scale || 1);
    star(ctx, x, yy, 14 * S * sc, STICKER_COLOR[s.type] || th.accent);
  }
  return c;
}

export function canvasToBlob(canvas) {
  return new Promise((resolve) => { try { canvas.toBlob((b) => resolve(b), 'image/png'); } catch { resolve(null); } });
}

/** 공유: Web Share(files) → 실패 시 다운로드 링크. 반환 'shared'|'downloaded'|'failed' */
export async function shareCanvas(canvas, filename) {
  const blob = await canvasToBlob(canvas);
  if (!blob) return 'failed';
  try {
    const file = new File([blob], filename, { type: 'image/png' });
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: '오늘의 나' });
      return 'shared';
    }
  } catch (e) {
    if (e && e.name === 'AbortError') return 'cancelled';
  }
  try {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    return 'downloaded';
  } catch { return 'failed'; }
}

function drawTracked(ctx, text, x, y, tracking) {
  let cx = x;
  for (const ch of String(text)) { ctx.fillText(ch, cx, y); cx += ctx.measureText(ch).width + tracking; }
}
