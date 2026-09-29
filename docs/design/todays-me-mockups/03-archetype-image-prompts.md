# 오늘의 나 — 시그니처 아키타입 5종 일러스트 생성 프롬프트

작성 2026-09-03. DALL-E 3 · Midjourney 겸용. 5종 모두 같은 스타일 블록을 앞에 붙여 일관성을 유지한다.

## 공통 스타일 블록 (모든 프롬프트 앞에 그대로 붙임)

```
Flat chunky vector illustration, sticker style, bold uniform black outlines (thick, even weight), smooth flat color fills with no gradients, no shading, no texture. Playful, whimsical, charming mascot design in the style of modern Korean lifestyle app stickers. Chibi proportions: big round head, small soft body, stubby limbs, rounded simplified shapes. Minimal face: dot or arc eyes, tiny mouth, round pink blush. Pastel candy palette only: butter yellow #FFD84D, candy pink #F5A8D8, lavender #CDBFF7, sky blue #AFC9F5, mint #BFE8CF, olive #A9B86B, coral #E2593A, cream #FFF3D6, ink black #141414. Single character centered, full body, solid flat pastel background, generous margin around the character, 2–3 small floating props max, tiny four-point sparkle stars as accents. No text, no letters, no logo, no watermark, no realistic rendering, no 3D.
```

Midjourney 공통 파라미터: `--ar 1:1 --v 6.1 --style raw --s 180 --no text, gradient, 3d, realistic, shading`
첫 장이 마음에 들면 그 이미지 URL을 `--sref <url>`로 나머지 4종에 붙여 팔레트·선 굵기를 고정한다. 캐릭터 얼굴 통일은 `--cref`가 아니라 위 스타일 블록의 얼굴 규칙으로 잡는다(5종은 서로 다른 인물이므로 cref는 쓰지 않는다).

DALL-E 3는 파라미터 없이 프롬프트 본문만 넣는다. "sticker style" "flat vector"가 빠지면 3D로 튀므로 스타일 블록을 절대 줄이지 않는다.

## 아키타입별 프롬프트

- **1. Miracle Morning Dreamer (새벽 감성 야망가)**
  ```
  [공통 스타일 블록] A determined but sleepy young character at dawn, sitting cross-legged on a round lavender meditation cushion, wearing an oversized butter-yellow hoodie and a sky-blue sweatband. One hand holds a tall glass of water, the other rests on the knee in a meditation pose. Eyes: one eye a calm closed arc, the other half-open and drooping, with a tiny open-mouth yawn and a small floating "z" made of shapes (not a letter). A flat cream crescent moon and a small flat coral sun peek from opposite top corners to show 5 AM. Props: a round alarm clock with only hands (no numerals) pointing to five, and a small planner with three check marks drawn as tick shapes. Solid lavender #CDBFF7 background. Mood: ambitious, soft, slightly exhausted, lovable.
  ```

- **2. Micro-Wellness Sloth (마이크로 웰니스 나무늘보)**
  ```
  [공통 스타일 블록] An anthropomorphic sloth character with olive-green fur, a cream face mask marking, and a cozy mint hoodie, lying on its back on a perfectly made bed with a smooth cream blanket and one neatly fluffed pillow. Both eyes are serene closed arcs, tiny content smile, blush. Three small pastel circles rise from its nose in a gentle line to show slow deep breathing. One hand rests on its belly; the other holds a tiny sky-blue plant sprout in a pot. In the far corner, a small pastel dumbbell sits unused with a tiny sleeping snail on top. Solid mint #BFE8CF background. Mood: unhurried, protected, peaceful, proud of tiny habits.
  ```

- **3. Healthy Pleasure Foodie (헬시 플레저 미식가)**
  ```
  [공통 스타일 블록] An energetic gym-goer character wearing a coral tank top, sky-blue shorts, a butter-yellow sweatband and chunky sneakers, standing in a confident pose. One arm flexes a small round bicep; the other hand proudly lifts a fork with a big slice of strawberry protein cake topped with a single strawberry. A tall cream protein shaker with a lavender lid sits at the feet next to a small pastel dumbbell. Wide happy eyes, big open smile showing joy, blush. Two sparkle stars near the cake. Solid candy-pink #F5A8D8 background. Mood: guilt-free reward, playful balance of workout and treat, zero shame.
  ```

- **4. Ritual Fairy / Glass Mental Guardian (유리멘탈 리추얼 요정)**
  ```
  [공통 스타일 블록] A gentle fairy character with two small rounded flat wings in pale lavender, wearing a cream ritual robe with a candy-pink sash, sitting on the floor in a calm kneeling pose. An open journal lies in front with a tiny pen; a thin incense stick in a small holder releases one soft curling smoke line drawn as a single smooth wavy stroke; a small lit candle and a cup of tea sit nearby. Eyes are calm closed arcs with a soft smile and blush. Floating above one palm: a heart-shaped flat glass ornament in sky blue with one tiny crack, lovingly patched with a small cream bandage. Solid lavender #CDBFF7 background with a few sparkle stars. Mood: fragile but self-healing, tender, quiet ritual.
  ```

- **5. Baby God-Saeng (갓생 신생아)**
  ```
  [공통 스타일 블록] A cheerful baby character in a butter-yellow onesie with a tiny olive-green bib, wearing a small crooked cream paper crown. Standing proudly with chest out, holding one glass of water high in one hand like a trophy and a single round vitamin gummy in the other. Huge sparkling round eyes, big open grin with one tooth, strong blush. Confetti made of small pastel circles and four-point stars bursts around the head; a tiny coral ribbon medal is pinned to the onesie. Solid butter-yellow #FFD84D background. Mood: immense, adorable pride over a very small accomplishment, beginner energy.
  ```

## 산출물 규격과 검수 체크

| 용도 | 크기 | 비고 |
|---|---|---|
| 리빌 화면 스테이지 | 2048×2048 원본 → 250×250 렌더 | 배경은 아키타입 배경색 그대로 |
| 공유 카드 캐릭터 | 84×84 렌더 | 원본에서 캐릭터만 잘라 투명 배경 PNG로 |
| 컬렉션 슬롯 글리프 | 18×18 단색 SVG | 생성 이미지가 아니라 소품 하나(물컵·사프란·포크·하트·왕관)로 별도 제작 |

검수 시 탈락 기준: 그라디언트나 음영이 생김, 외곽선 굵기가 장면마다 다름, 글자가 박힘, 소품이 4개 이상, 팔레트 밖 색이 큰 면적을 차지함, 정면이 아닌 과한 원근. 5장을 나란히 놓고 머리 크기·선 굵기·눈 스타일이 같은지 본다.

## 브리프와의 관계 (결정 필요)

이 5종은 **성향형** 아키타입이다. 기존 브리프 §4의 7종은 **완료 조합형**(오늘 한 트랙 조합으로 결정)이다. 둘은 결정 규칙이 다르다.

| 선택지 | 결정 규칙 | 영향 |
|---|---|---|
| A. 5종이 7종을 대체 | 온보딩 문진 또는 최근 7일 행동 패턴으로 성향 배정, 하루 단위가 아니라 주 단위로 바뀜 | 브리프 §4, spec-03 §5-2·§6-1, 요건서 FR-C04·아키타입 사전 전면 수정. "오늘의 캐릭터"가 "이번 주의 나"로 바뀜 |
| B. 두 층 공존 | 7종 = 하루 결과 캐릭터(현행), 5종 = 사용자 프로필 성향(온보딩에서 1회 배정, 카드 테마·말투에 반영) | 브리프에 §4-2 "성향 아키타입" 추가만. 기획서 수정 최소 |
| C. 5종을 하루 조합에 매핑 | 예: 물+마음=Miracle Morning Dreamer, 마음만=Ritual Fairy, 물만=Baby God-Saeng, 활동+식이=Healthy Pleasure Foodie, 작은 습관만=Micro-Wellness Sloth | 조합 7개 대 캐릭터 5개라 2개 조합이 비거나 겹침. 이름은 재밌지만 규칙이 억지스러움 |

**B안 채택(2026-09-03, 사용자 확정).** 배정 규칙·반영 위치는 브리프 §4-2·§4-3, 개발 요건은 02-dev-requirements §2-6·§3·§4-6.
