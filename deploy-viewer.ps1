# 페르소나 테스트 뷰어 공개 배포 (외부 테스터용).
# persona_test_server.py 를 RUN_MODE=viewer 로 공개 Cloud Run 에 배포한다.
# 뷰어는 dev RAG(비공개 유지)를 서버-대-서버(메타데이터 SA 토큰)로 호출하므로
# 외부 사용자는 RAG 로그인 불필요. 개인화(방향2) ON 으로 시연.
# ※ 완전 공개 URL — 테스트 1건 = OpenAI 호출(비용). 악용 시 비용 증가 유의.
param(
    [string]$ProjectId   = "medical-compliance-tester",
    [string]$Region      = "asia-northeast3",
    [string]$ServiceName = "medical-rag-viewer",
    [string]$RagService  = "medical-rag-dev",
    [switch]$SkipBuild
)

$ImageUri = "gcr.io/${ProjectId}/${ServiceName}"

Write-Host "=== 페르소나 뷰어 공개 배포 ===" -ForegroundColor Cyan

# ── 대상 RAG URL 조회 (토큰 audience + 프록시 대상) ──
$RagUrl = gcloud run services describe $RagService --region $Region --format "value(status.url)" 2>$null
if (-not $RagUrl) { Write-Host "[ERROR] $RagService URL 조회 실패" -ForegroundColor Red; exit 1 }
Write-Host "RAG 대상 : $RagUrl"

# ── 이미지 빌드 (RAG와 동일 Dockerfile, 전체 복사) ──
if ($SkipBuild) {
    Write-Host "[1/3] Build skipped (-SkipBuild)" -ForegroundColor Yellow
} else {
    Write-Host "[1/3] Building image..." -ForegroundColor Yellow
    gcloud builds submit --tag $ImageUri .
    if ($LASTEXITCODE -ne 0) { Write-Host "Build failed!" -ForegroundColor Red; exit 1 }
}

# ── 배포 (공개, RUN_MODE=viewer, 개인화 ON) ──
Write-Host "[2/3] Deploying public viewer..." -ForegroundColor Yellow
$EnvVars = "RUN_MODE=viewer,RAG_DEV_URL=$RagUrl,PERSONA_RAG_URL=$RagUrl,PERSONAL_SIGNAL_TO_LLM=on,ALLOW_CROSS_BORDER_PERSONAL=on"
gcloud run deploy $ServiceName `
    --image $ImageUri `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --memory 512Mi --cpu 1 `
    --timeout 900 `
    --min-instances 0 --max-instances 3 `
    --concurrency 20 `
    --set-env-vars $EnvVars
if ($LASTEXITCODE -ne 0) { Write-Host "Deploy failed!" -ForegroundColor Red; exit 1 }

# ── 뷰어 런타임 SA 에 RAG run.invoker 부여 (서버-대-서버 호출) ──
Write-Host "[3/3] Granting run.invoker on $RagService ..." -ForegroundColor Yellow
$ViewerSA = gcloud run services describe $ServiceName --region $Region --format "value(spec.template.spec.serviceAccountName)" 2>$null
if (-not $ViewerSA) {
    $ProjNum = gcloud projects describe $ProjectId --format "value(projectNumber)" 2>$null
    $ViewerSA = "${ProjNum}-compute@developer.gserviceaccount.com"
}
Write-Host "뷰어 SA  : $ViewerSA"
gcloud run services add-iam-policy-binding $RagService --region $Region `
    --member="serviceAccount:$ViewerSA" --role="roles/run.invoker" | Out-Null

$url = gcloud run services describe $ServiceName --region $Region --format "value(status.url)" 2>$null
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  공개 뷰어 배포 완료: $ServiceName" -ForegroundColor Green
Write-Host "  외부 테스트 URL: $url" -ForegroundColor Green
Write-Host "  (완전 공개 · 개인화 방향2 ON · 합성 데이터)" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
