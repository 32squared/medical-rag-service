# 마이헬스케어 P0 프론트엔드 (모바일 웹 / PWA)

정본: [docs/plan/23-p0-detailed-design.md](../docs/plan/23-p0-detailed-design.md) §6.
결정(§22): **모바일 웹(React) + PWA**. P0 는 **빌드 무의존**(React UMD + htm CDN)으로
즉시 실행 — 프로덕션 전환 시 Vite/React 프로젝트 + `openapi-typescript` 타입드 클라이언트로 승격.

## 화면(플로우)
온보딩(웰컴→동의 토글) → 본인인증(PASS mock) → 홈(의료 채팅) · 설정(동의 grant/revoke·로그아웃·탈퇴).
동의·세션·개인화 게이트는 전부 BFF(동의원장) 기준. localStorage 에는 토큰만 보관.

## 실행
정적 서버로 서빙하고 BFF 를 띄운다(같은 오리진이면 CORS 불필요).

```bash
# 1) BFF 기동(다른 오리진이면 CORS 허용)
BFF_CORS_ORIGINS=http://localhost:5500 uvicorn bff.app:app --port 8080
# 2) web/ 정적 서빙
python -m http.server 5500 -d web
# 3) 브라우저에서 http://localhost:5500 접속
```

BFF 가 다른 오리진이면 콘솔에서 한 번 지정(우선순위 1):
```js
localStorage.setItem('mhc_bff', 'http://localhost:8080')
```
(미설정 시 `config.js`의 `window.__MHC_BFF__` → 그것도 비면 같은 오리진 호출.)

## 정적 호스팅 배포(프론트/BFF 분리) — 재배포 즉시반영
프론트는 GCS 공개버킷, BFF 는 API 전용 Cloud Run 으로 분리. **프론트 변경은 Docker 빌드 없이 수십 초**.
```powershell
.\deploy-web.ps1      # 버킷 생성/공개 + web/ rsync + config.js 에 BFF URL 주입 + BFF CORS 개방
```
- 앱 URL: `https://storage.googleapis.com/medical-rag-web-<projnum>/index.html`
- `config.js` — 런타임 BFF URL 주입 지점(버킷 배포본은 deploy-web.ps1 이 BFF 절대 URL 로 덮어씀; 리포 기본값은 빈 문자열=same-origin 하위호환 → BFF `/app` 마운트·로컬 그대로 동작).
- CORS: BFF `BFF_CORS_ORIGINS=https://storage.googleapis.com`(deploy-web.ps1 이 `--update-env-vars` 로 머지, deploy-bff.ps1 도 기본 포함 → 풀 재배포에도 유지).
- 인증=Bearer 토큰(localStorage)·쿠키 없음 → cross-origin 안전. 검증: 정적 오리진에서 전체 여정(인증→동의→페르소나→코칭) 응답 ACAO 전 단계 통과 확인.

## 구성
- `index.html` — SPA(React+htm), Warm Light 디자인 토큰(딥틸 #0E8A6B·앰버), 401 시 refresh 1회 자동 재시도
- `config.js` — 런타임 BFF 베이스 주입(정적 호스팅 분리용; SW 가 캐시 안 함 → 호스트별 값 항상 네트워크)
- `manifest.webmanifest` · `sw.js` — PWA(설치·앱셸 오프라인 캐시, API/크로스오리진은 캐시 금지) · `icon.svg`

## 상태/한계
P0 데모. 본인인증은 mock(같은 기기=같은 계정). iOS Safari 웹푸시 제약(§22 다운사이드)으로
리마인더 실푸시는 P3(Capacitor) 후속. 정식 빌드(Vite)·접근성 정밀화는 프로덕션 단계.
