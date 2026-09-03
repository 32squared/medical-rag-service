# 오늘의 나 (Today's Me) — 4화면 목업·세부기획 묶음

MZ세대 웰니스 루틴 앱 컨셉. 마이헬스케어 루틴 제품(정본 `docs/plan/27-routine-content.md`) 위에 얹는 재미 레이어로 가정.

## 읽는 순서

| 순서 | 파일 | 내용 |
|---|---|---|
| 1 | [00-concept-brief.md](00-concept-brief.md) | 공통 기준. Product Offer, 3트랙·원소, 아키타입 7종 결정 규칙, 채택된 공통 가정(환산 계수·기록일 경계·완료 판정), 비주얼 시스템, 기획서 공통 목차 |
| 2 | [01-cross-review.md](01-cross-review.md) | 관리자 교차 검수. 화면 간 충돌 판정 C1~C11, 채택 가정 A1~A8, 제품 오너 결정 대기 E1~E8 |
| 3 | [design.md](design.md) | **디자인 시스템 SSOT.** 팔레트 hex, 타이포 스케일, 간격·라운드·그림자·외곽선 토큰, 컴포넌트 Do/Don't, CSS 토큰 블록. 코딩 에이전트가 UI를 만들 때 첫 번째로 읽는다 |
| 3 | [02-dev-requirements.md](02-dev-requirements.md) | **개발 착수 문서.** 기존 코드 접점, 기능 요구사항 FR-xx와 수용 기준, 신규 테이블 4개, API 계약, 계산 규칙, 밴드 게이팅, 이벤트, 작업 분해 B1~Q1, 결정 대기 기본값 |
| 4 | [04-integration-plan.md](04-integration-plan.md) | 기존 앱 통합 계획. 현황 점검(간극 G1~G10), 결정 D1~D6, Phase 0~5 작업표, 파일 변경 지도, 리스크 |
| 4 | [03-archetype-image-prompts.md](03-archetype-image-prompts.md) | 웰니스 타입 5종(성향형) 일러스트 프롬프트. B안 채택: 7종 하루 캐릭터와 별도 층, 온보딩 문진 배정(브리프 §4-2·§4-3) |
| 5 | [spec-01-daily-tracker.md](spec-01-daily-tracker.md) | 화면 1 · 오늘의 체크인 (요소 ID T1-xx) |
| 6 | [spec-02-daily-stats.md](spec-02-daily-stats.md) | 화면 2 · 오늘의 기록 (T2-xx) |
| 7 | [spec-03-archetype-reveal.md](spec-03-archetype-reveal.md) | 화면 3 · 오늘의 캐릭터 리빌 (T3-xx) |
| 8 | [spec-04-share-card.md](spec-04-share-card.md) | 화면 4 · 공유 카드 (T4-xx) |

## 목업

- 캔버스(디자인 편집 가능): https://claude.ai/code/artifact/012a1ce7-41e5-49cd-9613-038f732118c4
- 작업 파일: `Main.dc.html`(화면 1) · `Stats.dc.html`(화면 2) · `Reveal.dc.html`(화면 3) · `Card.dc.html`(화면 4) · `canvas.json`(배치)
- 2페이지 "웰니스 타입": `TypeResult.dc.html`(온보딩 결과) · `TypeCard.dc.html`(타입 카드 1:1). 캐릭터 일러스트 5종은 `type-{dreamer,sloth,foodie,fairy,baby}.jpg`(600px, 원본 1254px PNG는 사용자 다운로드 폴더의 ChatGPT 생성본).
- `todays-me-wellness-mockups.html`은 위 작업 파일에서 생성한 배포본. 직접 편집하지 않고 작업 파일을 고친 뒤 재생성한다.

## 작성 방식

- 화면별 기획서 4건은 Opus 세션 4개가 병렬로 작성했고, 관리자 세션이 교차 검수(01-cross-review.md) 후 정정 지시를 내려 반영했다.
- 개발은 02-dev-requirements.md에서 시작한다. 화면 기획서는 각 화면의 요소·카피·상태 상세.
- 기획서 안의 "가정:" 표시는 정본에 없는 값이다. 브리프에 올라간 값은 잠정 확정, 01-cross-review §3의 E 항목은 제품 오너 결정이 필요하다.

## 목업 반영 대기

- 화면 1 주간 7점 스트립(스크롤 아래 영역)은 목업에 없음. C11 판정대로 above the fold 밖이라 정적 목업에서는 생략.
- 아키타입 7종 캐릭터 일러스트는 Balance Monk만 그려져 있음. 나머지 6종은 spec-03 설정표 기준으로 후속 작업.
