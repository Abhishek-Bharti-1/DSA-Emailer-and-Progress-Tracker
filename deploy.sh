#!/usr/bin/env bash
set -e

echo "🚀 Starting DSA Problems Emailer Google Cloud Deployment..."

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    echo "❌ No Google Cloud project selected! Run 'gcloud config set project <PROJECT_ID>' first."
    exit 1
fi

REGION="asia-south1"
echo "📌 Using Project ID: $PROJECT_ID"

# Read .env
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please ensure .env contains your API keys."
    exit 1
fi

set -a
source .env
set +a

# Secrets
echo "🔐 Configuring Secret Manager..."
for secret in GEMINI_API_KEY SENDER_EMAIL SENDER_PASSWORD RECIPIENT_EMAIL; do
    val="${!secret}"
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo -n "$val" | gcloud secrets versions add "$secret" --data-file=- --project="$PROJECT_ID" --quiet
    else
        echo -n "$val" | gcloud secrets create "$secret" --data-file=- --project="$PROJECT_ID" --quiet
    fi
done

# Service accounts
RUNNER_SA="dsa-emailer-runner@$PROJECT_ID.iam.gserviceaccount.com"
gcloud iam service-accounts create dsa-emailer-runner --display-name="dsa-emailer-runner" --project="$PROJECT_ID" 2>/dev/null || true
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$RUNNER_SA" --role="roles/datastore.user" --quiet >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$RUNNER_SA" --role="roles/secretmanager.secretAccessor" --quiet >/dev/null

INVOKER_SA="dsa-scheduler-invoker@$PROJECT_ID.iam.gserviceaccount.com"
gcloud iam service-accounts create dsa-scheduler-invoker --display-name="dsa-scheduler-invoker" --project="$PROJECT_ID" 2>/dev/null || true

# Deploy Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy dsa-emailer-service \
    --source . \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --service-account "$RUNNER_SA" \
    --no-allow-unauthenticated \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,SENDER_EMAIL=SENDER_EMAIL:latest,SENDER_PASSWORD=SENDER_PASSWORD:latest,RECIPIENT_EMAIL=RECIPIENT_EMAIL:latest" \
    --set-env-vars="SMTP_SERVER=smtp.gmail.com,SMTP_PORT=587,USE_FIRESTORE=true" \
    --timeout=300 \
    --memory=512Mi \
    --cpu=1 \
    --quiet

SERVICE_URL=$(gcloud run services describe dsa-emailer-service --region "$REGION" --project "$PROJECT_ID" --format="value(status.url)")
gcloud run services add-iam-policy-binding dsa-emailer-service --region "$REGION" --project "$PROJECT_ID" --member="serviceAccount:$INVOKER_SA" --role="roles/run.invoker" --quiet >/dev/null

# Scheduler
echo "📅 Configuring Cloud Scheduler..."
gcloud scheduler jobs create http dsa-daily-job \
    --location="$REGION" --project="$PROJECT_ID" \
    --schedule="0 8 * * *" --time-zone="Asia/Kolkata" \
    --uri="$SERVICE_URL/jobs/daily" --http-method=POST \
    --oidc-service-account-email="$INVOKER_SA" --oidc-token-audience="$SERVICE_URL" \
    2>/dev/null || gcloud scheduler jobs update http dsa-daily-job \
    --location="$REGION" --project="$PROJECT_ID" \
    --schedule="0 8 * * *" --time-zone="Asia/Kolkata" \
    --uri="$SERVICE_URL/jobs/daily" --http-method=POST \
    --oidc-service-account-email="$INVOKER_SA" --oidc-token-audience="$SERVICE_URL" --quiet

echo "🎉 Deployment complete!"
