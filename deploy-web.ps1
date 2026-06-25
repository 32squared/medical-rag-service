# web/ 정적 호스팅 배포 — GCS 공개 버킷에 SPA 업로드. **Docker 빌드 없음 → 프론트 즉시반영**.
# BFF(API)는 별도 Cloud Run(medical-rag-bff). 이 스크립트가:
#   (1) 버킷 생성/공개  (2) web/ rsync 업로드  (3) config.js 에 BFF 절대 URL 주입
#   (4) 셸/SW/config no-cache  (5) BFF CORS 개방(이미지 재빌드 없이 env 머지).
# 이후 프론트 변경은 이 스크립트만 재실행하면 됨(수십 초). BFF 코드 변경 시에만 deploy-bff.ps1.
param(
    [string]$ProjectId  = "medical-compliance-tester",
    [string]$Region     = "asia-northeast3",
    [string]$BffService = "medical-rag-bff",
    [string]$Bucket     = "",          # 비우면 medical-rag-web-<projectNumber>
    [switch]$SkipCors                  # CORS 갱신 생략(이미 열려 있을 때)
)

$ErrorActionPreference = "Stop"
Write-Host "=== web/ 정적 호스팅 배포(GCS) ===" -ForegroundColor Cyan

# 전역 고유 버킷명(프로젝트 번호 접미)
if (-not $Bucket) {
    $ProjNum = gcloud projects describe $ProjectId --format="value(projectNumber)"
    $Bucket  = "medical-rag-web-$ProjNum"
}
$Gs = "gs://$Bucket"
Write-Host "버킷    : $Gs"

# BFF URL(config.js 주입 + CORS 오리진 산출)
$BffUrl = gcloud run services describe $BffService --region $Region --project $ProjectId --format="value(status.url)"
if (-not $BffUrl) { Write-Host "[ERROR] $BffService URL 조회 실패" -ForegroundColor Red; exit 1 }
Write-Host "BFF URL : $BffUrl"

# [1/5] 버킷 생성(없으면) — 단일 리전, uniform 접근
$exists = $null
try { $exists = gcloud storage buckets describe $Gs --project $ProjectId --format="value(name)" 2>$null } catch {}
if (-not $exists) {
    Write-Host "[1/5] 버킷 생성..." -ForegroundColor Yellow
    gcloud storage buckets create $Gs --project $ProjectId --location $Region --uniform-bucket-level-access
    if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] 버킷 생성 실패" -ForegroundColor Red; exit 1 }
} else { Write-Host "[1/5] 버킷 존재 — 재사용" -ForegroundColor Green }

# [2/5] 공개 읽기(allUsers:objectViewer). 실패 = 조직정책 차단 → 경량 Cloud Run 폴백 필요.
Write-Host "[2/5] 공개 읽기 권한 부여..." -ForegroundColor Yellow
gcloud storage buckets add-iam-policy-binding $Gs --member=allUsers --role=roles/storage.objectViewer | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 공개권한 실패 — 조직정책(publicAccessPrevention) 가능성. 경량 정적 Cloud Run 으로 폴백하세요." -ForegroundColor Red
    exit 2
}

# [3/5] 업로드(rsync). --delete-unmatched: 소스에 없는 객체 제거. config.js 는 빈 채 올라간 뒤 4단계서 덮어씀.
Write-Host "[3/5] 업로드(rsync)..." -ForegroundColor Yellow
gcloud storage rsync web $Gs --recursive --delete-unmatched-destination-objects
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] 업로드 실패" -ForegroundColor Red; exit 1 }

# [4/5] config.js 에 BFF 절대 URL 주입(BOM 없는 UTF-8) + 셸/SW/config no-cache
Write-Host "[4/5] config.js 주입 + 캐시헤더..." -ForegroundColor Yellow
$cfg = "window.__MHC_BFF__ = `"$BffUrl`";`n"
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $cfg)   # .NET WriteAllText = UTF-8 no BOM
gcloud storage cp $tmp "$Gs/config.js" --content-type="text/javascript" --cache-control="no-cache, max-age=0" | Out-Null
Remove-Item $tmp -Force
gcloud storage objects update "$Gs/index.html" --cache-control="no-cache, max-age=0" | Out-Null
gcloud storage objects update "$Gs/sw.js"      --cache-control="no-cache, max-age=0" | Out-Null

# [5/5] BFF CORS 개방 — 이미지 재빌드 없이 env 머지(빠름). update-env-vars 는 기존 env 보존.
if (-not $SkipCors) {
    Write-Host "[5/5] BFF CORS 개방(update-env-vars)..." -ForegroundColor Yellow
    gcloud run services update $BffService --region $Region --project $ProjectId `
        --update-env-vars "BFF_CORS_ORIGINS=https://storage.googleapis.com" | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] CORS 갱신 실패 — 수동 확인 필요" -ForegroundColor Yellow }
} else { Write-Host "[5/5] CORS 갱신 생략(-SkipCors)" -ForegroundColor Gray }

$AppUrl = "https://storage.googleapis.com/$Bucket/index.html"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  web/ 정적 배포 완료" -ForegroundColor Green
Write-Host "  앱 URL : $AppUrl" -ForegroundColor Green
Write-Host "  BFF    : $BffUrl (CORS: storage.googleapis.com)" -ForegroundColor Gray
Write-Host "  이후 프론트만 바꿨다면 deploy-web.ps1 재실행(Docker 빌드 0)" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
