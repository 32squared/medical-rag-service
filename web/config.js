// 런타임 설정 — 정적 호스팅 시 BFF(API) 절대 URL 주입 지점.
// 기본값 비움 = same-origin (BFF 가 /app 으로 직접 서빙하거나 로컬 개발).
// 정적 호스팅(GCS 등) 배포 시 deploy-web.ps1 이 이 파일을 BFF 절대 URL 로 덮어씀.
// 개발자가 수동 오버라이드하려면 콘솔에서 localStorage.setItem('mhc_bff', 'https://...').
window.__MHC_BFF__ = window.__MHC_BFF__ || "";
