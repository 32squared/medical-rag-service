# RAG 운영 어드민 대시보드 배포 (비밀번호 보호, 공개 ingress).
# admin_server.py 를 RUN_MODE=admin 으로 공개 Cloud Run 에 배포. RAG(비공개)의 admin
# 집계 엔드포인트를 서버-대-서버(메타데이터 SA 토큰 + X-Admin-Secret)로 호출한다.
# 사람 접근은 ADMIN_PASSWORD 로그인으로 보호.
# RAG 이미지(medical-rag-dev)를 재사용하므로 별도 빌드 불필요(-SkipBuild 기본).
# ※ RAG 쪽에도 동일한 ADMIN_SECRET 을 env 로 설정해야 엔드포인트가 호출을 허용한다.
param(
    [Parameter(Mandatory=$true)][string]$AdminPassword,
    [Parameter(Mandatory=$true)][string]$AdminSecret,
    [string]$ProjectId   = "medical-compliance-tester",
    [string]$Region      = "asia-northeast3",
    [string]$ServiceName = "medical-rag-admin",
    [string]$RagService  = "medical-rag-dev",
    [string]$Image       = ""
)

if (-not $Image) { $Image = "gcr.io/${ProjectId}/${RagService}" }   # RAG 이미지 재사용

Write-Host "=== RAG 어드민 대시보드 배포 ===" -ForegroundColor Cyan
$RagUrl = gcloud run services describe $RagService --region $Region --format "value(status.url)" 2>$null
if (-not $RagUrl) { Write-Host "[ERROR] $RagService URL 조회 실패" -ForegroundColor Red; exit 1 }
Write-Host "RAG 대상 : $RagUrl"
Write-Host "이미지   : $Image (RAG 이미지 재사용)"

# ── 배포 (공개, RUN_MODE=admin, 비밀번호+시크릿) ──
$EnvVars = "RUN_MODE=admin,RAG_DEV_URL=$RagUrl,ADMIN_PASSWORD=$AdminPassword,ADMIN_SECRET=$AdminSecret"
gcloud run deploy $ServiceName `
    --image $Image `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --memory 512Mi --cpu 1 `
    --timeout 120 `
    --min-instances 0 --max-instances 2 `
    --concurrency 10 `
    --set-env-vars $EnvVars
if ($LASTEXITCODE -ne 0) { Write-Host "Deploy failed!" -ForegroundColor Red; exit 1 }

# ── 어드민 SA 에 RAG run.invoker 부여 ──
$SA = gcloud run services describe $ServiceName --region $Region --format "value(spec.template.spec.serviceAccountName)" 2>$null
if (-not $SA) {
    $ProjNum = gcloud projects describe $ProjectId --format "value(projectNumber)" 2>$null
    $SA = "${ProjNum}-compute@developer.gserviceaccount.com"
}
gcloud run services add-iam-policy-binding $RagService --region $Region `
    --member="serviceAccount:$SA" --role="roles/run.invoker" | Out-Null

$url = gcloud run services describe $ServiceName --region $Region --format "value(status.url)" 2>$null
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  어드민 대시보드 배포 완료: $ServiceName" -ForegroundColor Green
Write-Host "  URL  : $url" -ForegroundColor Green
Write-Host "  로그인: ADMIN_PASSWORD (배포 시 지정값)" -ForegroundColor Gray
Write-Host "  ※ RAG 에도 동일 ADMIN_SECRET 설정 필요:" -ForegroundColor Yellow
Write-Host "    gcloud run services update $RagService --region $Region --update-env-vars ADMIN_SECRET=<동일값>" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
