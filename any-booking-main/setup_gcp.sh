#!/usr/bin/env bash
# One-shot GCP setup script for AnyBooking.
# Run once before the first deploy. Safe to re-run — skips already-created resources.
set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
step() { echo -e "\n${GREEN}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
die()  { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

# ── Usage ──────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $0 [options]

Required:
  --project-id        GCP project ID (e.g. my-any-booking)
  --db-password       Password for the Cloud SQL anybooking_user
  --github-repo       GitHub repo in owner/repo format (e.g. josetonyin/any-booking)

Optional:
  --region            GCP region (default: us-central1)
  --razorpay-key-id   Razorpay key ID   (can be updated later via Secret Manager)
  --razorpay-key-secret  Razorpay secret (can be updated later via Secret Manager)
  --email-user        SMTP email address
  --email-password    SMTP app password
  --from-email        Default from address (default: "AnyBooking <noreply@anybooking.in>")
  --admin-email       Admin notification email (defaults to --email-user)
  --site-url          Public site URL — update after first deploy (default: placeholder)

Example:
  ./setup_gcp.sh \\
    --project-id my-any-booking \\
    --db-password "S3cur3P@ss!" \\
    --github-repo josetonyin/any-booking \\
    --email-user you@gmail.com \\
    --email-password xxxx-xxxx-xxxx-xxxx \\
    --admin-email you@gmail.com
EOF
  exit 1
}

# ── Defaults ───────────────────────────────────────────────────────────────────
REGION="us-central1"
PROJECT_ID=""
DB_PASSWORD=""
GITHUB_REPO=""
RAZORPAY_KEY_ID="PLACEHOLDER"
RAZORPAY_KEY_SECRET="PLACEHOLDER"
EMAIL_USER=""
EMAIL_PASSWORD=""
FROM_EMAIL="AnyBooking <noreply@anybooking.in>"
ADMIN_EMAIL=""
SITE_URL="https://PLACEHOLDER"

# ── Parse arguments ────────────────────────────────────────────────────────────
[[ $# -eq 0 ]] && usage

while [[ $# -gt 0 ]]; do
  case $1 in
    --project-id)          PROJECT_ID="$2";          shift 2 ;;
    --db-password)         DB_PASSWORD="$2";         shift 2 ;;
    --github-repo)         GITHUB_REPO="$2";         shift 2 ;;
    --region)              REGION="$2";              shift 2 ;;
    --razorpay-key-id)     RAZORPAY_KEY_ID="$2";     shift 2 ;;
    --razorpay-key-secret) RAZORPAY_KEY_SECRET="$2"; shift 2 ;;
    --email-user)          EMAIL_USER="$2";          shift 2 ;;
    --email-password)      EMAIL_PASSWORD="$2";      shift 2 ;;
    --from-email)          FROM_EMAIL="$2";          shift 2 ;;
    --admin-email)         ADMIN_EMAIL="$2";         shift 2 ;;
    --site-url)            SITE_URL="$2";            shift 2 ;;
    -h|--help)             usage ;;
    *) die "Unknown argument: $1. Run $0 --help for usage." ;;
  esac
done

# ── Validate required ──────────────────────────────────────────────────────────
[[ -z "$PROJECT_ID"   ]] && die "--project-id is required"
[[ -z "$DB_PASSWORD"  ]] && die "--db-password is required"
[[ -z "$GITHUB_REPO"  ]] && die "--github-repo is required (e.g. josetonyin/any-booking)"

EMAIL_USER="${EMAIL_USER:-PLACEHOLDER}"
EMAIL_PASSWORD="${EMAIL_PASSWORD:-PLACEHOLDER}"
ADMIN_EMAIL="${ADMIN_EMAIL:-$EMAIL_USER}"
SA_EMAIL="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

echo -e "${GREEN}"
echo "┌─────────────────────────────────────────────┐"
echo "│         AnyBooking — GCP Setup              │"
echo "└─────────────────────────────────────────────┘"
echo -e "${NC}"
echo "  Project ID  : ${PROJECT_ID}"
echo "  Region      : ${REGION}"
echo "  GitHub repo : ${GITHUB_REPO}"
echo "  SA email    : ${SA_EMAIL}"
echo ""

# ── 0. Set active project ──────────────────────────────────────────────────────
step "0. Setting active GCP project"
gcloud config set project "${PROJECT_ID}"

# ── 1. Enable APIs ─────────────────────────────────────────────────────────────
step "1. Enabling required GCP APIs"
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  storage.googleapis.com

# ── 2. Artifact Registry ───────────────────────────────────────────────────────
step "2. Creating Artifact Registry repository"
if gcloud artifacts repositories describe any-booking-repo \
     --location="${REGION}" &>/dev/null; then
  warn "Repository already exists — skipping"
else
  gcloud artifacts repositories create any-booking-repo \
    --repository-format=docker \
    --location="${REGION}"
fi

# ── 3. Cloud SQL ───────────────────────────────────────────────────────────────
step "3. Creating Cloud SQL instance (this takes ~5 minutes)"
if gcloud sql instances describe any-booking-db &>/dev/null; then
  warn "Cloud SQL instance already exists — skipping"
else
  gcloud sql instances create any-booking-db \
    --database-version=POSTGRES_16 \
    --edition=ENTERPRISE \
    --tier=db-f1-micro \
    --region="${REGION}" \
    --storage-auto-increase
fi

step "3a. Creating database"
if gcloud sql databases describe anybooking --instance=any-booking-db &>/dev/null; then
  warn "Database already exists — skipping"
else
  gcloud sql databases create anybooking --instance=any-booking-db
fi

step "3b. Creating database user"
gcloud sql users create anybooking_user \
  --instance=any-booking-db \
  --password="${DB_PASSWORD}" 2>/dev/null || \
gcloud sql users set-password anybooking_user \
  --instance=any-booking-db \
  --password="${DB_PASSWORD}"

# ── 4. Service Account ─────────────────────────────────────────────────────────
step "4. Creating GitHub Actions service account"
if gcloud iam service-accounts describe "${SA_EMAIL}" &>/dev/null; then
  warn "Service account already exists — skipping creation"
else
  gcloud iam service-accounts create github-deployer \
    --display-name="GitHub Actions Deployer"
fi

step "4a. Granting roles to service account"
for role in \
  roles/run.admin \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor \
  roles/cloudsql.client \
  roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --condition=None 2>/dev/null || true
  echo "  Granted ${role}"
done

step "4b. Granting Secret Manager and GCS access to the Cloud Run runtime service account"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None 2>/dev/null || true

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectAdmin" \
  --condition=None 2>/dev/null || true

# ── 4c. GCS media bucket ───────────────────────────────────────────────────────
MEDIA_BUCKET="${PROJECT_ID}-media"
step "4c. Creating GCS media bucket (${MEDIA_BUCKET})"
if gsutil ls "gs://${MEDIA_BUCKET}" &>/dev/null; then
  warn "Media bucket already exists — skipping"
else
  gsutil mb -l "${REGION}" "gs://${MEDIA_BUCKET}"
fi

# ── 5. Workload Identity Federation ────────────────────────────────────────────
step "5. Setting up Workload Identity Federation"
if gcloud iam workload-identity-pools describe github-pool \
     --location=global &>/dev/null; then
  warn "WIF pool already exists — skipping"
else
  gcloud iam workload-identity-pools create github-pool \
    --location=global \
    --display-name="GitHub Actions Pool"
fi

if gcloud iam workload-identity-pools providers describe github-provider \
     --location=global \
     --workload-identity-pool=github-pool &>/dev/null; then
  warn "WIF provider already exists — skipping"
else
  gcloud iam workload-identity-pools providers create-oidc github-provider \
    --location=global \
    --workload-identity-pool=github-pool \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}'"
fi

POOL_ID=$(gcloud iam workload-identity-pools describe github-pool \
  --location=global --format='value(name)')

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_REPO}" \
  2>/dev/null || true

# ── 6. Secret Manager ──────────────────────────────────────────────────────────
step "6. Storing secrets in Google Secret Manager"

# create_secret_once: creates the secret on first run; skips silently on re-run.
# Use for generated values (DJANGO_SECRET_KEY) that must never be rotated.
create_secret_once() {
  local name="$1" value="$2"
  if gcloud secrets describe "${name}" &>/dev/null; then
    warn "${name} already exists — skipping (run 'gcloud secrets versions add' to rotate)"
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" --data-file=-
    echo "  Created: ${name}"
  fi
}

# store_secret: creates on first run; updates on re-run only if a real value is
# supplied (not PLACEHOLDER). Placeholder values are skipped when the secret
# already exists, preventing accidental overwrites of real credentials.
store_secret() {
  local name="$1" value="$2"
  if gcloud secrets describe "${name}" &>/dev/null; then
    if [[ "${value}" == "PLACEHOLDER" ]]; then
      warn "${name} already exists — skipping placeholder update"
    else
      printf '%s' "${value}" | gcloud secrets versions add "${name}" --data-file=-
      echo "  Updated: ${name}"
    fi
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" --data-file=-
    echo "  Created: ${name}"
  fi
}

DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50), end='')")
DB_URL="postgres://anybooking_user:${DB_PASSWORD}@/anybooking?host=/cloudsql/${PROJECT_ID}:${REGION}:any-booking-db"

create_secret_once "DJANGO_SECRET_KEY"   "${DJANGO_SECRET_KEY}"
store_secret "DATABASE_URL"        "${DB_URL}"
store_secret "RAZORPAY_KEY_ID"     "${RAZORPAY_KEY_ID}"
store_secret "RAZORPAY_KEY_SECRET" "${RAZORPAY_KEY_SECRET}"
store_secret "EMAIL_HOST"          "smtp.gmail.com"
store_secret "EMAIL_HOST_USER"     "${EMAIL_USER}"
store_secret "EMAIL_HOST_PASSWORD" "${EMAIL_PASSWORD}"
store_secret "DEFAULT_FROM_EMAIL"  "${FROM_EMAIL}"
store_secret "ADMIN_NOTIFY_EMAIL"  "${ADMIN_EMAIL}"
store_secret "SITE_URL"            "${SITE_URL}"
store_secret "EMAIL_BACKEND"       "django.core.mail.backends.smtp.EmailBackend"
store_secret "GCS_MEDIA_BUCKET"    "${PROJECT_ID}-media"

# ── 7. GitHub Secrets ──────────────────────────────────────────────────────────
step "7. Setting GitHub Actions secrets"

WIF_PROVIDER=$(gcloud iam workload-identity-pools providers describe github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --format='value(name)')

gh secret set GCP_PROJECT_ID                 --body "${PROJECT_ID}"
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --body "${WIF_PROVIDER}"
gh secret set GCP_SERVICE_ACCOUNT            --body "${SA_EMAIL}"
gh secret set CLOUD_SQL_INSTANCE             --body "${PROJECT_ID}:${REGION}:any-booking-db"
gh secret set CLOUD_RUN_HOST                 --body "*"

# ── Done ───────────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}✓ GCP setup complete!${NC}\n"
cat <<EOF
Next steps:
  1. Push to main to trigger the first deploy:
       git commit --allow-empty -m "ci: initial deploy" && git push

  2. Allow public access (run once after deploy succeeds):
       gcloud run services add-iam-policy-binding any-booking \\
         --region=${REGION} --member=allUsers --role=roles/run.invoker

  3. Update CLOUD_RUN_HOST with the real hostname:
       URL=\$(gcloud run services describe any-booking \\
         --region=${REGION} --format='value(status.url)' | sed 's|https://||')
       gh secret set CLOUD_RUN_HOST --body "\$URL"

  4. Push once more to apply the correct ALLOWED_HOSTS:
       git commit --allow-empty -m "ci: set real CLOUD_RUN_HOST" && git push

  5. Update SITE_URL once the service is live:
       URL=\$(gcloud run services describe any-booking --region=${REGION} --format='value(status.url)')
       printf '%s' "\$URL" | gcloud secrets versions add SITE_URL --data-file=-
EOF
