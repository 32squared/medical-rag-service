# 오늘의 나 (Today's Me) — Design System `design.md`

Single source of truth for anyone (human or AI coding agent) building this app's UI. Values below are lifted from the shipped mockups (`Main/Stats/Reveal/Card/TypeResult/TypeCard.dc.html`) and the decisions in `00-concept-brief.md` · `01-cross-review.md` · `02-dev-requirements.md`. When this file and a mockup disagree, this file wins; when this file and the copy rules in `docs/plan/27-routine-content.md` disagree, the copy rules win.

Style in one line: **candy-pastel full-bleed screens, chunky flat vector characters with bold ink outlines, big-radius cards, black pill CTAs, zero guilt.**

---

## 1. Color Palette

All colors are flat fills. No gradients anywhere in UI. Illustrations may not use gradients either.

### 1-1. Core candy pastels (screen backgrounds & big surfaces)

| Token | Name | Hex | Used for |
|---|---|---|---|
| `--c-lemon` | Warm Lemon | `#FFD84D` | Screen 1 (Tracker) bg, Baby God-Saeng bg, active nav dot, star accents |
| `--c-lavender` | Lavender | `#CDBFF7` | Screen 2 (Stats) bg, mind/habit tile, Dreamer & Fairy bg |
| `--c-pink` | Candy Pink | `#F5A8D8` | Screen 3 (Reveal) bg, Foodie bg, blush, stacked-card accent |
| `--c-mint` | Soft Mint | `#BFE8CF` | Screen 4 (Share) bg, Sloth bg, Night Owl bg |
| `--c-peach` | Peach | `#FFC98F` | Sunny Runner bg (contrast still under verification) |
| `--c-sky` | Sky Blue | `#AFC9F5` | Water tile, decorative circles |
| `--c-olive` | Olive | `#A9B86B` | Action card fill, decorative flower, Sloth fur |
| `--c-cream` | Cream | `#FFF3D6` | Secondary pills, back cards, sash/robe fills |
| `--c-cream-2` | Warm Cream | `#FFF8EC` | Ring card surface |
| `--c-sage` | Sage | `#E4EBC7` | Zen Barista bg (contrast still under verification) |

### 1-2. Ink & neutrals

| Token | Hex | Used for |
|---|---|---|
| `--c-ink` | `#141414` | **Bold Dark Outline**, text, black pill CTAs, bottom nav, today-slot circle |
| `--c-ink-soft` | `#3A3A3A` | Sub-headline text on lemon |
| `--c-muted` | `#6B6B6B` | Captions on cream |
| `--c-muted-2` | `#7A7A7A` | 0 / unmeasured "–" state |
| `--c-white` | `#FFFFFF` | White pills, tiles, chips |
| `--c-toggle-off` | `#DDE6DF` | Switch track (off) |

Text-on-tint pairs (pre-checked, keep as-is): lemon→`#5A4A2B`, lavender→`#3E3260`, pink→`#4A2B3E` / `#5A2B48`, sky→`#2B3A5A`, mint→`#2F4A3A`.

### 1-3. Track & element colors (semantic, never swap)

| Track | Element | Fill | Tile bg | Accent/dot |
|---|---|---|---|---|
| 식이 기록 (diet) | Water drop | `#4C86F0` | `--c-sky` | `#4C86F0` |
| 활동 기록 (exercise) | Bolt | `#FFB800` | `--c-cream` | `#FF8A5B` |
| 생활 리듬 (habit) | Moon | `#8E7BEF` | `--c-lavender` | `#8E7BEF` |

### 1-4. Share-card themes (contrast ≥ 3:1 with ink text `#FFF3E0`)

| theme_id | Card bg | Display accent | Text |
|---|---|---|---|
| `coral` (default) | `#E2593A` | `--c-lemon` | `#FFF3E0` |
| `lavender` | `#7C6BD9` | `--c-lemon` | `#FFF3E0` |
| `forest` | `#4E7A5A` | `--c-lemon` | `#FFF3E0` |

`#FF7A59` (old coral) is **retired**: 2.35:1 contrast. Do not reintroduce.

### 1-5. Illustration skin & blush

Skin `#FFD9B8` · blush `#F5A7D6` at 85% · eyes/mouth strokes `--c-ink` 3–3.2px round caps.

### 1-6. Forbidden color usage

- No red (`#C8553D` or any) for missed/incomplete states. Missed days are grey `--c-muted-2` "–". Coral is a celebration color only.
- No gradients, no glassmorphism, no drop-shadow-on-text.
- Never introduce a new hue for a single element. Pick from the table; restyle by swapping tokens.

---

## 2. Typography

Three faces, one fallback stack each. Korean and Latin are split by font fallback so a single `font-family` declaration handles mixed text.

| Role | Family (Google Fonts) | Weights | Fallback |
|---|---|---|---|
| Display (Latin, numerals) | **Lexend** | 600 · 700 · 800 | `'Malgun Gothic', system-ui, sans-serif` |
| Display (Korean) | **Jua** | 400 (single) | same |
| Body & badges (Latin) | **Quicksand** | 600 · 700 | falls through to Gowun Dodum for Hangul |
| Body & badges (Korean) | **Gowun Dodum** | 400 | `'Malgun Gothic', system-ui, sans-serif` |

```css
:root {
  --font-display-latin: 'Lexend', 'Malgun Gothic', system-ui, sans-serif;
  --font-display-ko:    'Jua', 'Malgun Gothic', system-ui, sans-serif;
  --font-body:          'Quicksand', 'Gowun Dodum', 'Malgun Gothic', system-ui, sans-serif;
}
```

Load: `https://fonts.googleapis.com/css2?family=Lexend:wght@600;700;800&family=Jua&family=Quicksand:wght@600;700&family=Gowun+Dodum&display=swap`

### 2-1. Type scale

| Token | Size / line-height | Weight / face | Where |
|---|---|---|---|
| `--t-hero-num` | 58px / 0.95, tracking −0.03em | Lexend 800 | Share-card big numbers |
| `--t-display-xl` | 50px / 1 | Lexend 800 | Ring center count |
| `--t-display-lg` | 40px / 1, −0.02em | Lexend 800 | Archetype EN name, metric hero number |
| `--t-h1-ko` | 38px / 1.08, −0.01em | Jua | Screen headline ("오늘, 하나만 해볼까요") |
| `--t-h2-ko` | 34px / 1.1 | Jua | Type result name |
| `--t-h3-ko` | 27px / 1.25 | Jua | Action card text (≤30 chars, 2 lines) |
| `--t-h4-ko` | 22px / 1.2 | Jua | Archetype KO name |
| `--t-h5-ko` | 18–20px / 1.2 | Jua | Screen titles, card unit labels |
| `--t-h6-ko` | 15–17px | Jua | Tile labels, CTA labels |
| `--t-body` | 14px / 1.5 | body | Descriptions, lore |
| `--t-body-sm` | 13–13.5px / 1.45 | body | Chips, tags, rows |
| `--t-caption` | 12–12.5px / 1.4 | body | Meta captions (≤20 chars), tile status |
| `--t-micro` | 10.5–11px | Lexend 600/700 or body | Card labels, watermark, `TODAY'S ME` with 0.14em tracking |

### 2-2. Rules

- Numbers are **always Lexend**, never Jua or Quicksand (Jua digits look wobbly at hero size).
- Korean headlines are Jua only. Never bold-synthesize Jua or Gowun Dodum.
- Uppercase Latin labels (`TODAY'S ME`, `BABY GOD-SAENG`) get 0.10–0.14em tracking; nothing else is tracked.
- Copy budgets are hard limits, enforced in code: action text 30 chars, meta caption 20, coach line 30, button label 12, chip 24, toast 30, card comment 20.
- Support 200% font scaling: buttons grow (`min-height`, no fixed height) and labels may wrap to 2 lines; never clip.

---

## 3. Spacing, Radius, Shadow, Border

### 3-1. Layout

| Token | Value | Note |
|---|---|---|
| `--screen-w` | 390px | Design frame (iPhone 14 class). Fluid in code. |
| `--safe-top` | 56px | Reserved for the real status bar. **Never draw a fake one.** |
| `--page-x` | 22px | Screen horizontal padding |
| `--stack-gap` | 14–16px | Vertical gap between screen sections |
| `--row-gap` | 8–12px | Gap inside chip rows / tile rows |
| `--nav-h` | 64px | Bottom nav pill, floats 22px from bottom |
| `--cta-bottom` | 22px | Fixed CTA offset |

Spacing scale (use only these): `4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 22 · 24 · 28 · 32`.

### 3-2. Radius

| Token | Value | Applies to |
|---|---|---|
| `--r-xl` | 32px | Hero/ring cards, reveal stage cards |
| `--r-lg` | 28px | Standard cards, share card |
| `--r-md` | 24px | Track tiles, image tiles |
| `--r-sm` | 9–13px | Checkbox squares (9), inline mini pills (13) |
| `--r-pill` | 999px | All buttons, chips, nav, toggles |

Default card radius for anything not listed: **28px** (`--r-lg`). 24px is the *minimum* for any card-like surface.

### 3-3. Shadow

Flat by default. Only two surfaces get shadows:

| Token | Value | Applies to |
|---|---|---|
| `--shadow-card` | `0 18px 40px rgba(20,20,20,0.16)` | Share card / type card (the "physical" object) |
| `--shadow-stage` | `0 14px 30px rgba(20,20,20,0.12)` | Reveal / type-result image tile |

Nothing else (tiles, chips, nav) has a shadow. Depth is made by **stacking rotated cards** (−4°, +3°, +6°) behind the front surface, not by blur.

### 3-4. Borders & outlines

| Token | Value | Applies to |
|---|---|---|
| `--border-bold` | 3px `--c-ink` | Illustration outlines, sticker frames, `.card--sticker` variant |
| `--border-check` | 2px `--c-ink` | Empty checkbox / completion badge outline |
| `--border-dashed` | 2px dashed text-on-tint color | "Add sticker" placeholder |

UI cards are **outline-free** by default (flat fill only). The bold 3px outline lives on the illustration/sticker layer so the cast of characters reads as one family. Do not add 1px hairline borders anywhere.

### 3-5. Sizes

| Token | Value |
|---|---|
| Tap target minimum | 44×44px (chips, icons, toggles, collection slots that are tappable) |
| Primary CTA | height 60px, radius pill, `--c-ink` bg, white label 17px Jua + 18px arrow in `--c-lemon` |
| Secondary button | height 46–48px, white or cream bg |
| Icon button | 44px circle, 18–20px stroke icon |
| Inline chip | 36px height, 14px horizontal padding |
| Filter/format chip | 44px height |
| Completion badge | 26px square, radius 9 |
| Track tile | flex 1 × 122px |
| Collection slot | 34px circle (display only) |
| Icons | inline SVG, 24-grid, stroke 2–2.4px, round caps. **No emoji, no icon fonts.** |

### 3-6. Motion

| Token | Value |
|---|---|
| `--ease` | `cubic-bezier(.2,.8,.2,1)` |
| Wake-up (sleep → awake) | eyes 260ms + bounce 140ms, total ≤ 400ms |
| Ring fill | ≤ 900ms, staggered per segment |
| Reveal sequence | ≤ 2,500ms total (dim → gather → flip), tap to skip, 1 haptic, sound off by default |
| Theme swap on card | 180ms bg crossfade, text swaps instantly |
| `prefers-reduced-motion` | replace all with 120ms opacity fade |

---

## 4. Component Rules

### 4-1. Action card (오늘의 행동, checklist card)

Anatomy: meta pill (track · minutes) → action text (Jua 27, ≤30 chars, 2 lines) → 3-button row. Front card `--c-olive` on `--r-lg`, two rotated back cards (cream −4°, pink +3°). One 4-point star bleeds off the top-right corner.

**Do**
- Render exactly the three states from the copy source: `오늘 완료하기` / `못했어요` / `해당없음`; after completion show `완료 ✓ · 되돌리기` with a 5-minute undo window.
- Keep the action text server-provided; never concatenate or rewrite it client-side.
- Keep the card above the fold; track tiles directly below; everything after scrolls.

**Don't**
- Don't count or display incomplete items ("2개 남음"), streak-break countdowns, or red states.
- Don't show a full-screen celebration on completion (the only exception is the first-ever check-in, D1).
- Don't add a fourth button, a progress percentage, or a "skip" that isn't `못했어요`.

### 4-2. Track tiles (물 · 걸음 · 마음)

Anatomy: tile bg per track → character SVG top-left (44×52) → completion badge top-right (26px) → label (Jua 16) → status caption (12px).

**Do**
- Model two independent states per tile: `awake` (any input started) and `complete` (goal reached). Badge fills only on `complete`; character eyes open on `awake`.
- Sleeping = closed-arc eyes + one or two "z" glyphs drawn as SVG text; awake = dot eyes + smile + blush.
- Reset all three to sleeping at local midnight (with the 10-minute E01 grace).
- Steps: show `걸음은 조금 뒤에 들어와요` when sync is >30 min old; never show 0 as a fact.

**Don't**
- Don't derive `complete` on the client; read it from the API.
- Don't render empty cup slots or "x/6" fractions on the tile (that is a missed-count).
- Don't make the badge the tap target; the whole tile is the target (≥44px).

### 4-3. Progress stats (ring + metric cards)

Ring: 176px, stroke 22, three arcs (water `#4C86F0` 0–110°, activity `#FF8A5B` 120–230°, mind `#8E7BEF` 240–350°) with round caps and mini element badges at the arc ends. Center: Lexend 800 50px **count of completed tracks**, caption `트랙 모두 완료` / `트랙 완료`.

Metric cards: hero number Lexend 800 (40 / 32) + unit in Jua + a white conversion pill (`= 작은 화분 3개`). Water card shows **filled cups only**; steps card has the bolt character; mind card has the sleeping cloud.

**Do**
- Treat 0 and unmeasured identically: grey `--c-muted-2` "–" plus a caption; hide the conversion pill when the converted quantity is 0.
- Render `conversion_text`, `highlight.text`, `streak_text` verbatim from the API.
- Use the four CTA variants only: `오늘의 캐릭터 만나기` / `캐릭터 다시 보기` / back to today / `이번 주 기록 보기` (warning band).

**Don't**
- Don't show percentages, scores, averages, "better than last week", or any comparison to other users.
- Don't draw outlined/empty cups, ghost bars, or target lines.
- Don't animate the ring on every re-render; once per screen entry.

### 4-4. Avatar / archetype states

Three layers of character art, all in the same chunky-flat-outline style:

| Layer | Asset | Size | Where |
|---|---|---|---|
| Element mini (drop / bolt / moon) | inline SVG | 18–52px | Tiles, ring badges, tags, collection slots |
| Daily archetype (7) | SVG 200×200 viewBox | 250px stage, 84px card | Reveal screen, share card |
| Wellness type (5) | JPG/PNG 600px, opaque bg | 300px tile, 150px card tile | Onboarding result, type card |

**Do**
- Keep every character on a **solid pastel background that matches its archetype color**; place opaque illustrations inside a rounded tile (`--r-md`/`--r-xl`) rather than on top of another color.
- Faces: dot or arc eyes, tiny mouth, round blush at 85%. Closed arcs = calm/sleep, dots = awake, big highlight eyes = proud/excited.
- Reveal stage: image tile rotated −3°, cream back card +5/6°, lemon mid card −4°.
- Collection slots show only days that produced an archetype; today is the black circle with a lemon star, always rightmost.

**Don't**
- Don't render empty/locked/ghost slots, "N종 중 M종" completion bars, or rarity tiers (rare/epic).
- Don't auto-open the reveal; it is always opened by the user from the stats CTA.
- Don't mix outline weights: 3px on illustrations, none on UI.

### 4-5. Shareable archetype card

Formats: story 9:16 (1080×1920) and feed 1:1 (1080×1080). Preview scale on the 390 frame is 254×452 (×4.25). Card radius `--r-lg`, `--shadow-card`, preview rotated −2°.

Anatomy (top → bottom): `TODAY'S ME` + date (Lexend 11) → up to three hero stats (Lexend 800 58 + Jua unit) → archetype EN (Lexend 800, `--c-lemon`) + KO/`이달 12%` line → character 84px bottom-right → footer `오늘의 나` + `{타입명} 타입`.

**Do**
- Build the payload from the whitelist only: `date_label, brand_label, metrics[≤3], archetype_en, archetype_ko, archetype_lore, rarity_pct, theme_id, stickers[≤6], comment(≤20), hide_numbers, wellness_type_label`. Unknown key → refuse to render.
- `hide_numbers=true` removes metrics and rarity from the payload before render (not just CSS-hidden).
- Drop stat rows for tracks not completed; never show a row as 0.
- Stickers: 5 types (star, cloud, bolt, drop, moon), max 6 total, max 3 per type, 44px tray targets.
- Every share failure falls back to `이미지 저장`.

**Don't**
- Don't put any of these on a card, ever: blood pressure, glucose, BMI, band/zone labels, streak breaks, missed counts, rankings, the user's name or photo.
- Don't regenerate a card after lock (00:10 next day); don't offer "다시 만들기".
- Don't use the retired coral `#FF7A59`; don't drop text contrast below 3:1 on any theme.

### 4-6. Global don'ts (copy & safety, from the copy source of truth)

- No disease labels, no health-outcome promises, no dosage/prescription phrasing.
- No rankings, leaderboards, level/badge systems, or rewards tied to health-band changes.
- Warning/emergency band: hide archetype, cards, collection, and streak text; show the medical-priority banner pinned at top.
- Never write "실패 · 결석 · 미달 · 놓친 날"; a skipped day is `쉬어간 날`.

---

## 5. CSS token block (copy into `tokens.css`)

```css
:root {
  /* color */
  --c-lemon:#FFD84D; --c-lavender:#CDBFF7; --c-pink:#F5A8D8; --c-mint:#BFE8CF;
  --c-peach:#FFC98F; --c-sky:#AFC9F5; --c-olive:#A9B86B; --c-cream:#FFF3D6;
  --c-cream-2:#FFF8EC; --c-sage:#E4EBC7;
  --c-ink:#141414; --c-ink-soft:#3A3A3A; --c-muted:#6B6B6B; --c-muted-2:#7A7A7A;
  --c-white:#FFFFFF; --c-toggle-off:#DDE6DF;
  --c-water:#4C86F0; --c-bolt:#FFB800; --c-bolt-accent:#FF8A5B; --c-moon:#8E7BEF;
  --c-skin:#FFD9B8; --c-blush:#F5A7D6;
  --c-theme-coral:#E2593A; --c-theme-lavender:#7C6BD9; --c-theme-forest:#4E7A5A; --c-card-text:#FFF3E0;

  /* type */
  --font-display-latin:'Lexend','Malgun Gothic',system-ui,sans-serif;
  --font-display-ko:'Jua','Malgun Gothic',system-ui,sans-serif;
  --font-body:'Quicksand','Gowun Dodum','Malgun Gothic',system-ui,sans-serif;

  /* layout */
  --safe-top:56px; --page-x:22px; --stack-gap:16px; --row-gap:10px; --nav-h:64px; --cta-bottom:22px;

  /* radius */
  --r-xl:32px; --r-lg:28px; --r-md:24px; --r-sm:12px; --r-pill:999px;

  /* border & shadow */
  --border-bold:3px; --border-check:2px;
  --shadow-card:0 18px 40px rgba(20,20,20,.16);
  --shadow-stage:0 14px 30px rgba(20,20,20,.12);

  /* motion */
  --ease:cubic-bezier(.2,.8,.2,1); --dur-wake:400ms; --dur-ring:900ms; --dur-reveal-max:2500ms;

  /* sizes */
  --tap-min:44px; --cta-h:60px; --btn-h:48px; --chip-h:36px; --tile-h:122px;
}
```

---

## 6. File map

| Need | Look at |
|---|---|
| Pixel reference per screen | `Main.dc.html` (1) · `Stats.dc.html` (2) · `Reveal.dc.html` (3) · `Card.dc.html` (4) · `TypeResult.dc.html` · `TypeCard.dc.html` |
| Character art | `type-*.jpg` (5 wellness types) · Balance Monk SVG inside `Reveal.dc.html` · element SVGs inside `Main.dc.html` |
| Copy & states per screen | `spec-01…04-*.md` |
| Data, API, gating | `02-dev-requirements.md` |
| Copy rules that override everything | `docs/plan/27-routine-content.md` §0 |
