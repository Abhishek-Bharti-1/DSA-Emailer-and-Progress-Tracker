# ==============================================================================
# DSA Problems Daily Emailer — Automated Google Cloud Deployment Script
# Targets: Cloud Run + Cloud Firestore + Secret Manager + Cloud Scheduler
# ==============================================================================

Write-Host "`n🚀 Starting DSA Problems Emailer Google Cloud Deployment..." -ForegroundColor Cyan

# 1. Determine Project ID & Project Number
$PROJECT_ID = $env:PROJECT_ID
if (-not $PROJECT_ID) {
    $PROJECT_ID = (gcloud config get-value project 2>$null)
    if ($PROJECT_ID) { $PROJECT_ID = $PROJECT_ID.Trim() }
}

if (-not $PROJECT_ID -or $PROJECT_ID -eq "(unset)") {
    Write-Host "❌ No Google Cloud project selected! Run 'gcloud config set project <PROJECT_ID>' or set `$env:PROJECT_ID first." -ForegroundColor Red
    exit 1
}

Write-Host "📌 Using Project ID: $PROJECT_ID" -ForegroundColor Green
$REGION = "asia-south1"

$PROJECT_NUMBER = (gcloud projects describe $PROJECT_ID --format="value(projectNumber)" 2>$null)
if ($PROJECT_NUMBER) { $PROJECT_NUMBER = $PROJECT_NUMBER.Trim() }
Write-Host "📌 Project Number: $PROJECT_NUMBER" -ForegroundColor Green

# 2. Ensure Cloud Build & Container APIs are enabled
Write-Host "`n🔧 Ensuring Build, Firestore & Container APIs are enabled..." -ForegroundColor Cyan
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com run.googleapis.com firestore.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com --project=$PROJECT_ID --quiet

# 3. Grant required build permissions to default Compute Service Account (required by Cloud Build)
Write-Host "🔑 Granting Cloud Build permissions to default service accounts..." -ForegroundColor Cyan
$COMPUTE_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

$buildRoles = @(
    "roles/serviceusage.serviceUsageConsumer",
    "roles/logging.logWriter",
    "roles/artifactregistry.writer"
)

foreach ($role in $buildRoles) {
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$COMPUTE_SA" `
        --role="$role" `
        --condition=None `
        --quiet | Out-Null
}

# 4. Check & Create Firestore Database if not exists
Write-Host "`n📦 Checking Cloud Firestore database..." -ForegroundColor Cyan
$existingDbs = @(gcloud firestore databases list --project=$PROJECT_ID --format="value(name)" 2>$null)
$dbExists = $false
foreach ($db in $existingDbs) {
    if ($db -match "projects/$PROJECT_ID/databases/\(default\)" -or $db -eq "(default)") {
        $dbExists = $true
        break
    }
}

if (-not $dbExists) {
    Write-Host "  • Creating Firestore (default) database in $REGION..." -ForegroundColor Yellow
    gcloud firestore databases create --location=$REGION --type=firestore-native --project=$PROJECT_ID --quiet
    Write-Host "✅ Firestore (default) database created." -ForegroundColor Green
} else {
    Write-Host "✅ Firestore (default) database already exists." -ForegroundColor Green
}

# 5. Parse secrets from .env
$envFilePath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFilePath)) {
    Write-Host "❌ .env file not found at $envFilePath! Please ensure .env contains your API keys." -ForegroundColor Red
    exit 1
}

$envVars = @{}
Get-Content $envFilePath | ForEach-Object {
    $line = $_.Trim().Replace("`u{feff}", "")
    if ($line -and -not ($line.StartsWith("#")) -and ($line -match "^([^=]+)=(.*)$")) {
        $key = $matches[1].Trim().Replace("`u{feff}", "")
        $val = $matches[2].Trim().Trim('"').Trim("'").Replace("`u{feff}", "")
        $envVars[$key] = $val
    }
}

$requiredKeys = @("GEMINI_API_KEY", "SENDER_EMAIL", "SENDER_PASSWORD", "RECIPIENT_EMAIL")
foreach ($key in $requiredKeys) {
    if (-not $envVars.ContainsKey($key) -or -not $envVars[$key]) {
        Write-Host "❌ Missing required key '$key' in .env file!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ Successfully loaded credentials from .env" -ForegroundColor Green

# 6. Create or update Secret Manager secrets (Strict UTF-8 without BOM)
Write-Host "`n🔐 Configuring Secret Manager secrets (without BOM)..." -ForegroundColor Cyan
$existingSecrets = @(gcloud secrets list --project=$PROJECT_ID --format="value(name)" 2>$null)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Set-Secret($name, $value) {
    $cleanValue = $value.Trim().Replace("`u{feff}", "")
    $tempFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($tempFile, $cleanValue, $utf8NoBom)
        if ($existingSecrets -contains $name) {
            Write-Host "  • Updating existing secret with clean payload: $name"
            gcloud secrets versions add $name --data-file=$tempFile --project=$PROJECT_ID --quiet
        } else {
            Write-Host "  • Creating new secret: $name"
            gcloud secrets create $name --data-file=$tempFile --project=$PROJECT_ID --quiet
        }
    } finally {
        if (Test-Path $tempFile) { Remove-Item $tempFile -Force -ErrorAction SilentlyContinue }
    }
}

Set-Secret "GEMINI_API_KEY" $envVars["GEMINI_API_KEY"]
Set-Secret "SENDER_EMAIL" $envVars["SENDER_EMAIL"]
Set-Secret "SENDER_PASSWORD" $envVars["SENDER_PASSWORD"]
Set-Secret "RECIPIENT_EMAIL" $envVars["RECIPIENT_EMAIL"]

# 7. Service Account for Cloud Run (Runner)
Write-Host "`n👤 Setting up Cloud Run Service Account (dsa-emailer-runner)..." -ForegroundColor Cyan
$RUNNER_SA = "dsa-emailer-runner@$PROJECT_ID.iam.gserviceaccount.com"
$existingSAs = @(gcloud iam service-accounts list --project=$PROJECT_ID --format="value(email)" 2>$null)

if ($existingSAs -notcontains $RUNNER_SA) {
    Write-Host "  • Creating service account: $RUNNER_SA"
    gcloud iam service-accounts create dsa-emailer-runner `
        --description="Service account for DSA Emailer Cloud Run execution" `
        --display-name="dsa-emailer-runner" `
        --project=$PROJECT_ID `
        --quiet
} else {
    Write-Host "  • Service account already exists: $RUNNER_SA"
}

# Grant permissions to Runner SA
Write-Host "  • Granting Firestore user role..."
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$RUNNER_SA" `
    --role="roles/datastore.user" `
    --condition=None `
    --quiet | Out-Null

Write-Host "  • Granting Secret Manager accessor role..."
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$RUNNER_SA" `
    --role="roles/secretmanager.secretAccessor" `
    --condition=None `
    --quiet | Out-Null

# 8. Service Account for Cloud Scheduler (Invoker)
Write-Host "`n⏰ Setting up Cloud Scheduler Invoker Account (dsa-scheduler-invoker)..." -ForegroundColor Cyan
$INVOKER_SA = "dsa-scheduler-invoker@$PROJECT_ID.iam.gserviceaccount.com"
if ($existingSAs -notcontains $INVOKER_SA) {
    Write-Host "  • Creating scheduler invoker account: $INVOKER_SA"
    gcloud iam service-accounts create dsa-scheduler-invoker `
        --description="Service account for Cloud Scheduler to invoke Cloud Run" `
        --display-name="dsa-scheduler-invoker" `
        --project=$PROJECT_ID `
        --quiet
} else {
    Write-Host "  • Scheduler invoker account already exists: $INVOKER_SA"
}

# 9. Deploy to Cloud Run
Write-Host "`n🚀 Deploying container to Cloud Run (dsa-emailer-service)..." -ForegroundColor Cyan
$deployCmd = @(
    "run", "deploy", "dsa-emailer-service",
    "--source=.",
    "--region=$REGION",
    "--project=$PROJECT_ID",
    "--service-account=$RUNNER_SA",
    "--no-allow-unauthenticated",
    "--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest,SENDER_EMAIL=SENDER_EMAIL:latest,SENDER_PASSWORD=SENDER_PASSWORD:latest,RECIPIENT_EMAIL=RECIPIENT_EMAIL:latest",
    "--set-env-vars=SMTP_SERVER=smtp.gmail.com,SMTP_PORT=587,USE_FIRESTORE=true",
    "--timeout=300",
    "--memory=512Mi",
    "--cpu=1",
    "--quiet"
)
& gcloud @deployCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Cloud Run deployment failed. Please review the build errors above." -ForegroundColor Red
    exit 1
}

# Retrieve the deployed service URL
$SERVICE_URL = (gcloud run services describe dsa-emailer-service --region=$REGION --project=$PROJECT_ID --format="value(status.url)" 2>$null)
if ($SERVICE_URL) { $SERVICE_URL = $SERVICE_URL.Trim() }

if (-not $SERVICE_URL) {
    Write-Host "❌ Could not retrieve Cloud Run Service URL." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Cloud Run successfully deployed at: $SERVICE_URL" -ForegroundColor Green

# Grant invoker permission to Scheduler Invoker SA
Write-Host "  • Authorizing Scheduler Invoker SA on Cloud Run..."
gcloud run services add-iam-policy-binding dsa-emailer-service `
    --region=$REGION `
    --project=$PROJECT_ID `
    --member="serviceAccount:$INVOKER_SA" `
    --role="roles/run.invoker" `
    --quiet | Out-Null

# 10. Configure Cloud Scheduler Jobs
Write-Host "`n📅 Configuring Cloud Scheduler Jobs..." -ForegroundColor Cyan
$existingJobs = @(gcloud scheduler jobs list --location=$REGION --project=$PROJECT_ID --format="value(ID)" 2>$null)

function Setup-Scheduler-Job($jobName, $schedule, $endpoint) {
    $targetUri = "$SERVICE_URL$endpoint"
    if ($existingJobs -contains $jobName) {
        Write-Host "  • Updating existing schedule for $jobName..."
        gcloud scheduler jobs update http $jobName `
            --location=$REGION `
            --project=$PROJECT_ID `
            --schedule="$schedule" `
            --time-zone="Asia/Kolkata" `
            --uri="$targetUri" `
            --http-method=POST `
            --oidc-service-account-email="$INVOKER_SA" `
            --oidc-token-audience="$SERVICE_URL" `
            --quiet | Out-Null
    } else {
        Write-Host "  • Creating schedule for $jobName..."
        gcloud scheduler jobs create http $jobName `
            --location=$REGION `
            --project=$PROJECT_ID `
            --schedule="$schedule" `
            --time-zone="Asia/Kolkata" `
            --uri="$targetUri" `
            --http-method=POST `
            --oidc-service-account-email="$INVOKER_SA" `
            --oidc-token-audience="$SERVICE_URL" `
            --quiet | Out-Null
    }
}

# Daily at 8:00 AM IST
Setup-Scheduler-Job "dsa-daily-job" "0 8 * * *" "/jobs/daily"

# Weekly on Sunday at 9:00 AM IST
Setup-Scheduler-Job "dsa-weekly-job" "0 9 * * 0" "/jobs/weekly"

Write-Host "`n🎉 DEPLOYMENT COMPLETE! All systems are live and scheduled." -ForegroundColor Green
Write-Host "------------------------------------------------------------------"
Write-Host "To test run your daily email immediately, run:"
Write-Host "  gcloud scheduler jobs run dsa-daily-job --location=$REGION" -ForegroundColor Yellow
Write-Host "To view real-time execution logs:"
Write-Host "  gcloud beta run services logs tail dsa-emailer-service --region=$REGION" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------------`n"
