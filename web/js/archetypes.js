// archetypes.js — 오늘의 나 재미 레이어 캐릭터 사전(원소 3종 · 하루 아키타입 7종 · 웰니스 타입 5종).
// 정본: docs/design/todays-me-mockups/design.md §4-4, 00-concept-brief.md §4·§4-2.
// 원칙: 인라인 SVG만(이모지·아이콘 폰트 금지). 캐릭터는 청키 플랫 벡터, 검정 스트로크 3px, 볼터치 85%.
// 서버가 내려주는 archetype_id / type_id 만 받아 여기 사전으로 그린다(클라이언트 판정 금지).

const INK = '#141414';
const SKIN = '#FFD9B8';
const BLUSH = '#F5A7D6';

// ── 원소 미니 캐릭터(트랙 타일·링 배지·태그·슬롯) ───────────────
// state: 'sleep' | 'awake' | 'plain'
export function elementSvg(kind, state = 'plain', size = 44) {
  const s = state;
  const eyes = (l, r, y) => (s === 'sleep'
    ? `<path d="M${l - 4} ${y}q4 -3 8 0" stroke="${INK}" stroke-width="2" fill="none" stroke-linecap="round"/>
       <path d="M${r - 4} ${y}q4 -3 8 0" stroke="${INK}" stroke-width="2" fill="none" stroke-linecap="round"/>`
    : `<circle cx="${l}" cy="${y}" r="2.4" fill="${INK}"/><circle cx="${r}" cy="${y}" r="2.4" fill="${INK}"/>`);
  const mouth = (x, y) => (s === 'awake'
    ? `<path d="M${x - 5} ${y}q5 4 10 0" stroke="${INK}" stroke-width="2" fill="none" stroke-linecap="round"/>` : '');
  const blush = (l, r, y) => (s === 'awake'
    ? `<circle cx="${l}" cy="${y}" r="3" fill="${BLUSH}" opacity=".8"/><circle cx="${r}" cy="${y}" r="3" fill="${BLUSH}" opacity=".8"/>` : '');
  const zz = (x, y) => (s === 'sleep'
    ? `<text x="${x}" y="${y}" font-family="Lexend,sans-serif" font-size="11" font-weight="700" fill="${INK}">z</text>` : '');
  if (kind === 'water') {
    return `<svg width="${size}" height="${size * 66 / 60}" viewBox="0 0 60 66" aria-hidden="true">
      <path d="M30 4C30 4 8 30 8 44a22 22 0 0 0 44 0C52 30 30 4 30 4Z" fill="#4C86F0"/>
      ${eyes(23, 37, 42)}${mouth(30, 49)}${blush(18, 42, 48)}${zz(46, 14)}</svg>`;
  }
  if (kind === 'bolt') {
    return `<svg width="${size}" height="${size * 70 / 60}" viewBox="0 0 60 70" aria-hidden="true">
      <path d="M36 4L12 40h20l-6 26 26-36H34z" fill="#FFB800"/>
      ${eyes(25, 33, 32)}${mouth(29, 39)}${zz(44, 14)}</svg>`;
  }
  return `<svg width="${size}" height="${size}" viewBox="0 0 64 64" aria-hidden="true">
    <path d="M40 6A26 26 0 1 0 58 48 20 20 0 1 1 40 6Z" fill="#8E7BEF"/>
    ${eyes(26, 36, 30)}${mouth(31, 40)}${zz(46, 18)}</svg>`;
}

// ── 하루 아키타입 7종 ───────────────────────────────────────────
// 공통 몸체 + 아키타입별 소품. viewBox 0 0 200 200.
function base({ robe = '#A9B86B', sash = '#FFF3D6', cushion = '#8E7BEF', eyes = 'closed', halo = null }) {
  const eyeSvg = eyes === 'open'
    ? `<circle cx="83" cy="86" r="4" fill="${INK}"/><circle cx="117" cy="86" r="4" fill="${INK}"/>`
    : eyes === 'wink'
      ? `<path d="M74 84q9 7 18 0" stroke="${INK}" stroke-width="3.2" fill="none" stroke-linecap="round"/><circle cx="117" cy="86" r="4" fill="${INK}"/>`
      : `<path d="M74 84q9 7 18 0" stroke="${INK}" stroke-width="3.2" fill="none" stroke-linecap="round"/>
         <path d="M108 84q9 7 18 0" stroke="${INK}" stroke-width="3.2" fill="none" stroke-linecap="round"/>`;
  return `
    <ellipse cx="100" cy="176" rx="74" ry="16" fill="${cushion}"/>
    ${halo ? `<ellipse cx="100" cy="36" rx="34" ry="8" fill="none" stroke="${halo}" stroke-width="6"/>` : ''}
    <path d="M40 172C40 128 62 108 100 108s60 20 60 64z" fill="${robe}"/>
    <path d="M100 108c-8 12-12 34-8 64h16c4-30 0-52-8-64z" fill="${sash}"/>
    <rect x="88" y="132" width="24" height="34" rx="12" fill="${SKIN}"/>
    <circle cx="100" cy="82" r="46" fill="${SKIN}"/>
    ${eyeSvg}
    <path d="M91 102q9 7 18 0" stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"/>
    <circle cx="68" cy="98" r="6" fill="${BLUSH}" opacity=".85"/><circle cx="132" cy="98" r="6" fill="${BLUSH}" opacity=".85"/>`;
}
const DROP = (x, y, s = 1) => `<path transform="translate(${x} ${y}) scale(${s})" d="M0 0C0 0-12 14-12 22a12 12 0 0 0 24 0C12 14 0 0 0 0Z" fill="#4C86F0"/>`;
const BOLT = (x, y, s = 1) => `<path transform="translate(${x} ${y}) scale(${s})" d="M6 0l-12 18h10l-3 14 13-18h-9z" fill="#FFB800"/>`;
const MOON = (x, y, s = 1) => `<path transform="translate(${x} ${y}) scale(${s})" d="M10 0a14 14 0 1 0 10 22 10 10 0 1 1-10-22z" fill="#8E7BEF"/>`;

const CHAR = {
  hydration_king: () => base({ robe: '#4C86F0', sash: '#FFF3D6', cushion: '#AFC9F5', eyes: 'open' })
    + `<path d="M76 46l8-16 8 10 8-14 8 14 8-10 8 16z" fill="#4C86F0"/>${DROP(100, 20, .8)}
       <rect x="126" y="126" width="22" height="40" rx="8" fill="#FFF3D6"/><rect x="124" y="120" width="26" height="10" rx="4" fill="#4C86F0"/>`,
  step_wizard: () => base({ robe: '#FF8A5B', sash: '#FFF3D6', cushion: '#FFD84D', eyes: 'open' })
    + `<path d="M60 52L100 4l40 48z" fill="${INK}"/><path d="M100 14l3 9 9 3-9 3-3 9-3-9-9-3 9-3z" fill="#FFD84D"/>
       <rect x="148" y="90" width="6" height="70" rx="3" fill="${INK}"/>${BOLT(150, 72, 1.2)}`,
  mindful_warrior: () => base({ robe: '#FFF3D6', sash: '#8E7BEF', cushion: '#CDBFF7', eyes: 'closed' })
    + `<rect x="52" y="56" width="96" height="14" rx="7" fill="#8E7BEF"/>${MOON(92, 50, .6)}
       <rect x="24" y="150" width="26" height="14" rx="3" fill="${INK}"/>`,
  sunny_runner: () => base({ robe: '#4C86F0', sash: '#FF8A5B', cushion: '#FFC98F', eyes: 'open' })
    + `<rect x="52" y="54" width="96" height="14" rx="7" fill="#FFD84D"/>
       <rect x="138" y="118" width="16" height="40" rx="6" fill="#4C86F0"/><rect x="141" y="110" width="10" height="10" rx="3" fill="#AFC9F5"/>
       <path d="M18 150h30M14 162h26" stroke="#FFF3D6" stroke-width="5" stroke-linecap="round"/>`,
  night_owl_reformed: () => base({ robe: '#CDBFF7', sash: '#FFF3D6', cushion: '#BFE8CF', eyes: 'wink' })
    + `<path d="M58 60l6-30 22 18zM142 60l-6-30-22 18z" fill="#8E7BEF"/><path d="M58 60a46 46 0 0 1 84 0z" fill="#8E7BEF"/>
       <circle cx="146" cy="140" r="16" fill="#FFD84D" stroke="${INK}" stroke-width="3"/><path d="M146 132v8h6" stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"/>`,
  zen_barista: () => base({ robe: '#FFF3D6', sash: '#A9B86B', cushion: '#E4EBC7', eyes: 'closed' })
    + `<path d="M76 108h48v56H76z" fill="#A9B86B"/>
       <path d="M22 130h26v26a13 13 0 0 1-26 0z" fill="#FFF3D6"/><path d="M48 136h8a6 6 0 0 1 0 12h-8" stroke="#FFF3D6" stroke-width="4" fill="none"/>
       <path d="M30 120q4-8 0-16M40 120q4-8 0-16" stroke="#7A7A7A" stroke-width="2.5" fill="none" stroke-linecap="round"/>${DROP(162, 110, .9)}`,
  balance_monk: () => base({ robe: '#A9B86B', sash: '#FFF3D6', cushion: '#8E7BEF', eyes: 'closed', halo: '#FFB800' })
    + `${DROP(30, 60, 1)}${BOLT(170, 48, 1)}${MOON(154, 118, 1)}`,
};

export const ARCHETYPES = {
  hydration_king: { nameEn: 'Hydration King', nameKo: '수분왕', bg: '#AFC9F5', elements: ['water'] },
  step_wizard: { nameEn: 'Step Wizard', nameKo: '걸음술사', bg: '#FFD84D', elements: ['bolt'] },
  mindful_warrior: { nameEn: 'Mindful Warrior', nameKo: '마음의 전사', bg: '#CDBFF7', elements: ['moon'] },
  sunny_runner: { nameEn: 'Sunny Runner', nameKo: '햇살 러너', bg: '#FFC98F', elements: ['water', 'bolt'] },
  night_owl_reformed: { nameEn: 'Night Owl, Reformed', nameKo: '개과천선 올빼미', bg: '#BFE8CF', elements: ['bolt', 'moon'] },
  zen_barista: { nameEn: 'Zen Barista', nameKo: '젠 바리스타', bg: '#E4EBC7', elements: ['water', 'moon'] },
  balance_monk: { nameEn: 'Balance Monk', nameKo: '밸런스 수도승', bg: '#F5A8D8', elements: ['water', 'bolt', 'moon'] },
};

export function archetypeSvg(id, size = 250) {
  const fn = CHAR[id] || CHAR.balance_monk;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 200 200" aria-hidden="true">${fn()}</svg>`;
}

/** 컬렉션 슬롯 글리프 — 아키타입별 원소 조합을 18px 로. */
export function slotSvg(id) {
  const a = ARCHETYPES[id];
  if (!a) return '';
  if (id === 'balance_monk') return `<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2c1 6 4 9 10 10-6 1-9 4-10 10-1-6-4-9-10-10 6-1 9-4 10-10z" fill="#FFD84D"/></svg>`;
  const sz = a.elements.length > 1 ? 11 : 18;
  return a.elements.map((e) => elementSvg(e, 'plain', sz)).join('');
}

// ── 웰니스 타입 5종(성향 층) ────────────────────────────────────
export const WELLNESS_TYPES = {
  miracle_morning_dreamer: { nameKo: '새벽 감성 야망가', nameEn: 'MIRACLE MORNING DREAMER', bg: '#CDBFF7', img: 'img/type-dreamer.jpg', traits: ['새벽 5시', '물과 명상', '저녁엔 방전'] },
  micro_wellness_sloth: { nameKo: '마이크로 웰니스 나무늘보', nameEn: 'MICRO-WELLNESS SLOTH', bg: '#BFE8CF', img: 'img/type-sloth.jpg', traits: ['이불 정리', '3분 호흡', '마음의 평화'] },
  healthy_pleasure_foodie: { nameKo: '헬시 플레저 미식가', nameEn: 'HEALTHY PLEASURE FOODIE', bg: '#F5A8D8', img: 'img/type-foodie.jpg', traits: ['운동 후 보상', '고단백 간식', '죄책감 없음'] },
  ritual_fairy: { nameKo: '유리멘탈 리추얼 요정', nameEn: 'RITUAL FAIRY', bg: '#CDBFF7', img: 'img/type-fairy.jpg', traits: ['향과 일기', '호흡', '스스로 복구'] },
  baby_godsaeng: { nameKo: '갓생 신생아', nameEn: 'BABY GOD-SAENG', bg: '#FFD84D', img: 'img/type-baby.jpg', traits: ['작게 시작', '스스로 칭찬', '기본 테마 코랄'] },
};

// ── 공용 아이콘(스트로크 SVG) ─────────────────────────────────────
export const ICON = {
  star: (c = '#FFD84D', s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2c1 6 4 9 10 10-6 1-9 4-10 10-1-6-4-9-10-10 6-1 9-4 10-10z" fill="${c}"/></svg>`,
  arrow: (c = '#FFD84D', s = 18) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>`,
  check: (c = '#FFFFFF', s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>`,
  close: (c = INK, s = 18) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>`,
  flame: (c = '#E2593A', s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3c1 4 5 6 5 11a5 5 0 0 1-10 0c0-2 1-3 1-3s0 3 2 3c1 0 1-2 0-4-1-3 1-6 2-7z"/></svg>`,
  cup: (fill = '#4C86F0', s = 34) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h14l-1.5 16a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2z" fill="${fill}"/><path d="M5.6 9h12.8" stroke="#FFFFFF" stroke-width="1.5" opacity=".6"/></svg>`,
  cupEmpty: (s = 34) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h14l-1.5 16a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2z" fill="none" stroke="${INK}" stroke-width="1.6" stroke-linejoin="round" opacity=".35"/></svg>`,
  cloud: (s = 70) => `<svg width="${s}" height="${s * 52 / 80}" viewBox="0 0 80 52" aria-hidden="true"><path d="M20 44a12 12 0 0 1-2-23.8A18 18 0 0 1 52 16a13 13 0 0 1 12 28z" fill="#FFFFFF"/><path d="M30 30q4-3 8 0M44 30q4-3 8 0" stroke="${INK}" stroke-width="1.8" fill="none" stroke-linecap="round"/><circle cx="28" cy="36" r="2.5" fill="${BLUSH}"/><circle cx="54" cy="36" r="2.5" fill="${BLUSH}"/></svg>`,
};
