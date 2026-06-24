# P0 BFF(FastAPI) 공개 배포 — 마이헬스케어 앱.
# RUN_MODE=bff 로 web/ SPA(/app) + 인증·동의·RAG 프록시를 공개 Cloud Run 에 배포.
# RAG 는 medical-rag-dev(비공개)를 SA 토큰으로 호출. 동의/계정은 Cloud SQL(PG).
# 주의: 본인인증은 데모 mock(APP_ENV 미설정=dev). 완전 공개 데모.
param(
    [string]$ProjectId   = "medical-compliance-tester",
    [string]$Region      = "asia-northeast3",
    [string]$ServiceName = "medical-rag-bff",
    [string]$RagService  = "medical-rag-dev",
    [string]$SqlInstance = "medical-db",
    [string]$DbName      = "medical_app_dev",
    [string]$DbPassword  = "",
    [string]$TokenSecret = "",
    [string]$CiHmacKey   = "",
    [string]$DataGoKrKey = "",
    [switch]$SkipBuild
)

$ImageUri = "gcr.io/${ProjectId}/${ServiceName}"
$SqlConnection = "${ProjectId}:${Region}:${SqlInstance}"

Write-Host "=== P0 BFF 공개 배포 ===" -ForegroundColor Cyan

# RAG URL 조회(토큰 audience + 프록시 대상)
$RagUrl = gcloud run services describe $RagService --region $Region --format "value(status.url)" 2>$null
if (-not $RagUrl) { Write-Host "[ERROR] $RagService URL 조회 실패" -ForegroundColor Red; exit 1 }
Write-Host "RAG 대상 : $RagUrl"

# DB 비밀번호(param > env > secret)
if (-not $DbPassword) { $DbPassword = $env:DB_PASSWORD }
if (-not $DbPassword) {
    try { $DbPassword = gcloud secrets versions access latest --secret=db-password --project=$ProjectId 2>$null } catch {}
}
if (-not $DbPassword) { Write-Host "[ERROR] DB 비밀번호 없음(-DbPassword 또는 db-password 시크릿)" -ForegroundColor Red; exit 1 }
$DatabaseUrl = "postgresql://app_user:${DbPassword}@/${DbName}?host=/cloudsql/${SqlConnection}"

# BFF 보안 시크릿(미지정 시 랜덤 — 재배포마다 세션 리셋)
if (-not $TokenSecret) { $TokenSecret = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N") }
if (-not $CiHmacKey)   { $CiHmacKey   = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N") }

# 공공데이터 키(시설 실검색) — param > env > .env (커밋 금지, .env는 gitignore)
if (-not $DataGoKrKey) { $DataGoKrKey = $env:DATA_GO_KR_KEY }
if (-not $DataGoKrKey -and (Test-Path ".env")) {
    $line = (Get-Content ".env" | Where-Object { $_ -match '^\s*DATA_GO_KR_KEY\s*=' } | Select-Object -First 1)
    if ($line) { $DataGoKrKey = ($line -replace '^\s*DATA_GO_KR_KEY\s*=\s*', '').Trim().Trim('"') }
}
if ($DataGoKrKey) { Write-Host "DATA_GO_KR_KEY: **** (시설 실검색 활성)" -ForegroundColor Green }
else { Write-Host "DATA_GO_KR_KEY 없음 — 시설은 데모 데이터로 동작" -ForegroundColor Yellow }

# 이미지 빌드(RAG 와 동일 Dockerfile, 전체 복사)
if ($SkipBuild) {
    Write-Host "[1/3] Build skipped (-SkipBuild)" -ForegroundColor Yellow
} else {
    Write-Host "[1/3] Building image..." -ForegroundColor Yellow
    gcloud builds submit --tag $ImageUri .
    if ($LASTEXITCODE -ne 0) { Write-Host "Build failed!" -ForegroundColor Red; exit 1 }
}

# 배포(공개, RUN_MODE=bff, Cloud SQL + VPC)
Write-Host "[2/3] Deploying public BFF..." -ForegroundColor Yellow
$EnvVars = "RUN_MODE=bff,RAG_URL=$RagUrl,RAG_GRAPH=SUPERVISED_HYBRID_SEARCH,DATABASE_URL=$DatabaseUrl,BFF_TOKEN_SECRET=$TokenSecret,ACCOUNT_CI_HMAC_KEY=$CiHmacKey"
if ($DataGoKrKey) { $EnvVars = "$EnvVars,DATA_GO_KR_KEY=$DataGoKrKey" }
gcloud run deploy $ServiceName `
    --image $ImageUri `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --memory 512Mi --cpu 1 `
    --timeout 900 `
    --min-instances 0 --max-instances 3 `
    --concurrency 20 `
    --execution-environment gen2 `
    --set-env-vars $EnvVars `
    --set-secrets "DB_PASSWORD=db-password:latest" `
    --add-cloudsql-instances $SqlConnection `
    --vpc-connector=medical-connector `
    --vpc-egress=private-ranges-only
if ($LASTEXITCODE -ne 0) { Write-Host "Deploy failed!" -ForegroundColor Red; exit 1 }

# BFF 런타임 SA 에 RAG run.invoker 부여(서버-대-서버 호출)
Write-Host "[3/3] Granting run.invoker on $RagService ..." -ForegroundColor Yellow
$BffSA = gcloud run services describe $ServiceName --region $Region --format "value(spec.template.spec.serviceAccountName)" 2>$null
if (-not $BffSA) {
    $ProjNum = gcloud projects describe $ProjectId --format "value(projectNumber)" 2>$null
    $BffSA = "${ProjNum}-compute@developer.gserviceaccount.com"
}
Write-Host "BFF SA   : $BffSA"
gcloud run services add-iam-policy-binding $RagService --region $Region `
    --member="serviceAccount:$BffSA" --role="roles/run.invoker" | Out-Null

$url = gcloud run services describe $ServiceName --region $Region --format "value(status.url)" 2>$null
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BFF 배포 완료: $ServiceName" -ForegroundColor Green
Write-Host "  앱 URL: $url/app/" -ForegroundColor Green
Write-Host "  (공개 데모 · mock 본인인증 · 동의/계정=Cloud SQL · RAG=$RagService)" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
