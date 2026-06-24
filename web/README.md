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

BFF 가 다른 오리진이면 콘솔에서 한 번 지정:
```js
localStorage.setItem('mhc_bff', 'http://localhost:8080')
```
(미설정 시 같은 오리진 호출 — BFF 가 web 을 함께 서빙하는 배포에 적합.)

## 구성
- `index.html` — SPA(React+htm), Warm Light 디자인 토큰(딥틸 #0E8A6B·앰버), 401 시 refresh 1회 자동 재시도
- `manifest.webmanifest` · `sw.js` — PWA(설치·앱셸 오프라인 캐시, API 응답은 캐시 금지) · `icon.svg`

## 상태/한계
P0 데모. 본인인증은 mock(같은 기기=같은 계정). iOS Safari 웹푸시 제약(§22 다운사이드)으로
리마인더 실푸시는 P3(Capacitor) 후속. 정식 빌드(Vite)·접근성 정밀화는 프로덕션 단계.
