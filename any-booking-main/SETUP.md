# AnyBooking — Setup Guide

---

## Google Cloud Deployment (Cloud Run + Cloud SQL PostgreSQL)

### Architecture
```
GitHub (push to main)
  └── GitHub Actions
        ├── 1. Run tests (against ephemeral Postgres)
        ├── 2. Build Docker image → push to Artifact Registry
        └── 3. Deploy to Cloud Run
                └── Cloud SQL Auth Proxy (socket) → Cloud SQL PostgreSQL
```

### Prerequisites

**Install required CLI tools:**

| Tool | Install | Verify |
|---|---|---|
| Google Cloud CLI | [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install) | `gcloud --version` |
| GitHub CLI | `brew install gh` (macOS) or [cli.github.com](https://cli.github.com) | `gh --version` |
| Python 3.11+ | `brew install python@3.11` (macOS) | `python3 --version` |

**Authenticate both CLIs:**
```bash
gcloud auth login
gh auth login
```

**You also need a GCP project with billing enabled:**

**Use an existing project:**
```bash
gcloud projects list          # find your project ID
gcloud config set project YOUR_PROJECT_ID
```

**Or create a new one:**
```bash
gcloud projects create any-booking-prod --name="AnyBooking"
gcloud config set project any-booking-prod

# Link a billing account (required for Cloud Run, Cloud SQL, Secret Manager)
gcloud billing accounts list
gcloud billing projects link any-booking-prod \
  --billing-account=XXXXXX-XXXXXX-XXXXXX
```

**Set a shell variable** so you don't have to substitute it in every command below:
```bash
export PROJECT_ID=$(gcloud config get-value project)
```

> All commands in this guide that show `YOUR_PROJECT_ID` can use `${PROJECT_ID}` once the variable is set. Always use curly braces (`${PROJECT_ID}`, not `$PROJECT_ID`) — in zsh, `$PROJECT_ID:us-central1` is misread as an uppercase modifier, silently corrupting the value.

### One-time GCP setup

Run the setup script — it handles all steps automatically and is safe to re-run:

```bash
./setup_gcp.sh \
  --project-id YOUR_PROJECT_ID \
  --db-password "CHOOSE_A_STRONG_PASSWORD" \
  --github-repo josetonyin/any-booking \
  --email-user your@gmail.com \
  --email-password xxxx-xxxx-xxxx-xxxx \
  --admin-email your@gmail.com
```

Razorpay credentials are optional at setup time — add them later via Secret Manager:
```bash
echo -n "rzp_live_XXXX" | gcloud secrets versions add RAZORPAY_KEY_ID --data-file=-
echo -n "your_secret"   | gcloud secrets versions add RAZORPAY_KEY_SECRET --data-file=-
```

The script performs these steps in order (skipping any that already exist):
1. Enable required GCP APIs
2. Create Artifact Registry repository
3. Create Cloud SQL instance, database, and user
4. Create `github-deployer` service account and grant all required roles
5. Grant the Cloud Run runtime service account Secret Manager access
6. Set up Workload Identity Federation (keyless GitHub Actions auth)
7. Store all secrets in Google Secret Manager
8. Set all GitHub Actions secrets via `gh` CLI

> **Note:** Cloud SQL creation takes ~5 minutes. The script waits automatically.

<details>
<summary>Manual steps (reference only)</summary>

#### 1. Enable APIs
```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com
```

#### 2. Create Artifact Registry repository
```bash
gcloud artifacts repositories create any-booking-repo \
  --repository-format=docker \
  --location=us-central1
```

#### 3. Create Cloud SQL PostgreSQL instance
```bash
gcloud sql instances create any-booking-db \
  --database-version=POSTGRES_16 \
  --edition=ENTERPRISE \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-auto-increase

gcloud sql databases create anybooking --instance=any-booking-db
gcloud sql users create anybooking_user \
  --instance=any-booking-db \
  --password=CHOOSE_A_STRONG_PASSWORD
```

#### 4. Create a Service Account for GitHub Actions
```bash
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer"

SA_EMAIL="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

for role in roles/run.admin roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor roles/cloudsql.client \
  roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" --role="${role}"
done

# Grant Cloud Run runtime SA Secret Manager access
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### 5. Set up Workload Identity Federation
```bash
gcloud iam workload-identity-pools create github-pool \
  --location=global --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='josetonyin/any-booking'"

POOL_ID=$(gcloud iam workload-identity-pools describe github-pool \
  --location=global --format='value(name)')

gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/josetonyin/any-booking"
```

#### 6. Store secrets in Google Secret Manager

> Use `gcloud secrets create` the first time. To update an existing secret later, replace `create` with `versions add`.

```bash
echo -n $(python3 -c "import secrets; print(secrets.token_urlsafe(50))") | \
  gcloud secrets create DJANGO_SECRET_KEY --data-file=-

# Write DATABASE_URL via temp file to avoid shell parsing issues
cat > /tmp/db_url.txt << 'EOF'
postgres://anybooking_user:PASSWORD@/anybooking?host=/cloudsql/PROJECT_ID:us-central1:any-booking-db
EOF
gcloud secrets create DATABASE_URL --data-file=/tmp/db_url.txt && rm /tmp/db_url.txt

echo -n "rzp_live_XXXX"    | gcloud secrets create RAZORPAY_KEY_ID --data-file=-
echo -n "your_secret"      | gcloud secrets create RAZORPAY_KEY_SECRET --data-file=-
echo -n "smtp.gmail.com"   | gcloud secrets create EMAIL_HOST --data-file=-
echo -n "your@gmail.com"   | gcloud secrets create EMAIL_HOST_USER --data-file=-
echo -n "your-app-password"| gcloud secrets create EMAIL_HOST_PASSWORD --data-file=-
echo -n "AnyBooking <noreply@anybooking.in>" | gcloud secrets create DEFAULT_FROM_EMAIL --data-file=-
echo -n "admin@anybooking.in" | gcloud secrets create ADMIN_NOTIFY_EMAIL --data-file=-
echo -n "https://your-cloud-run-url" | gcloud secrets create SITE_URL --data-file=-
echo -n "django.core.mail.backends.smtp.EmailBackend" | gcloud secrets create EMAIL_BACKEND --data-file=-
```

#### 7. Set GitHub Secrets
```bash
WIF_PROVIDER=$(gcloud iam workload-identity-pools providers describe github-provider \
  --location=global --workload-identity-pool=github-pool --format='value(name)')

gh secret set GCP_PROJECT_ID                 --body "${PROJECT_ID}"
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --body "${WIF_PROVIDER}"
gh secret set GCP_SERVICE_ACCOUNT           --body "github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
gh secret set CLOUD_SQL_INSTANCE            --body "${PROJECT_ID}:us-central1:any-booking-db"
```

> Secret names must be all caps with underscores only — no spaces, no hyphens.

</details>

The CI/CD pipeline automatically mounts all secrets on every deploy: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `ADMIN_NOTIFY_EMAIL`, and `SITE_URL`. No GitHub secret is needed for these — they are read from Google Secret Manager at deploy time.

### Deployment flow
Once the above is configured, every push to `main`:
1. Runs Django checks + tests against a fresh Postgres container
2. Builds the Docker image and pushes to Artifact Registry
3. Deploys the new image to Cloud Run (zero-downtime rolling update)
4. Migrations run automatically on container startup

Cloud Run is configured with: 0–10 instances (scales to zero when idle), 512 Mi RAM, 1 vCPU, 80 concurrent requests per instance, 120 s request timeout.

### First deploy — post-deploy steps

After the first successful deploy:

**1. Get the deployed URL:**
```bash
gcloud run services describe any-booking \
  --region=us-central1 \
  --format='value(status.url)'
```

Set it as a shell variable for the steps below:
```bash
FULL_URL=$(gcloud run services describe any-booking \
  --region=us-central1 \
  --format='value(status.url)')
echo "$FULL_URL"
```

**2. Allow public access** (Cloud Run blocks all unauthenticated requests by default):
```bash
gcloud run services add-iam-policy-binding any-booking \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

**3. Update the GitHub secret for ALLOWED_HOSTS:**
```bash
gh secret set CLOUD_RUN_HOST --body "${FULL_URL#https://}"
```

Then push a commit or re-run the workflow so `ALLOWED_HOSTS` is set to the real hostname (not `*`).

**4. Update SITE_URL** (used to build links in outgoing emails):
```bash
printf '%s' "$FULL_URL" | gcloud secrets versions add SITE_URL --data-file=-
```

**5. Create the admin superuser:**

Use the helper script (see `create_admin.sh`):
```bash
./create_admin.sh \
  --project-id my-any-booking \
  --username admin \
  --email admin@example.com \
  --password "ChangeMe123!"
```

Or run manually:
```bash
# Get the latest image
IMAGE=$(gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/${PROJECT_ID}/any-booking-repo/any-booking \
  --sort-by="~CREATE_TIME" --limit=1 \
  --format="value(IMAGE,DIGEST)" | awk '{print $1"@"$2}')

gcloud run jobs create create-superuser \
  --image="$IMAGE" \
  --region=us-central1 \
  --set-cloudsql-instances="${PROJECT_ID}:us-central1:any-booking-db" \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=DJANGO_SECRET_KEY:latest" \
  --command="python" \
  --args="manage.py,createsuperuser,--noinput,--username,admin,--email,admin@example.com" \
  --set-env-vars="DJANGO_SUPERUSER_PASSWORD=ChangeMe123!" \
  --execute-now
```

> Change the username, email, and password before running. To reset a password later, use `changepassword` instead of `createsuperuser`.

**6. Seed data** — run one-time setup commands via Cloud Run Jobs:

The Excel file must be accessible to the container. Upload it to Cloud Storage first, then run the job.

**Upload halls.xlsx to Cloud Storage:**
```bash
# Create the bucket (once)
gsutil mb -l us-central1 gs://${PROJECT_ID}-uploads

# Grant Cloud Run runtime service account read access
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
gsutil iam ch \
  serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com:objectViewer \
  gs://${PROJECT_ID}-uploads

# Upload the file
gsutil cp halls.xlsx gs://${PROJECT_ID}-uploads/halls.xlsx
```

**Get the latest image (set once per session):**
```bash
IMAGE=$(gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/${PROJECT_ID}/any-booking-repo/any-booking \
  --sort-by="~CREATE_TIME" --limit=1 \
  --format="value(IMAGE,DIGEST)" | awk '{print $1"@"$2}')
```

**Import banquet hall data from Excel:**
```bash
gcloud run jobs create import-halls \
  --image="$IMAGE" \
  --region=us-central1 \
  --set-cloudsql-instances="${PROJECT_ID}:us-central1:any-booking-db" \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=DJANGO_SECRET_KEY:latest" \
  --command="bash" \
  --args="-c,python -c \"from google.cloud import storage; storage.Client().bucket('${PROJECT_ID}-uploads').blob('halls.xlsx').download_to_filename('/tmp/halls.xlsx')\" && python manage.py import_halls /tmp/halls.xlsx" \
  --execute-now
```

**Seed sample data for all categories + international locations (optional):**
```bash
gcloud run jobs create seed-sample-data \
  --image="$IMAGE" \
  --region=us-central1 \
  --set-cloudsql-instances="${PROJECT_ID}:us-central1:any-booking-db" \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=DJANGO_SECRET_KEY:latest" \
  --command="python" \
  --args="manage.py,seed_sample_data" \
  --execute-now
```

> If a job already exists, delete it first with `gcloud run jobs delete JOB_NAME --region=us-central1 --quiet`, then recreate. Or re-execute without changes: `gcloud run jobs execute JOB_NAME --region=us-central1`.

### Teardown — delete all GCP resources

Run these commands to fully remove the stack. **This is irreversible** — all data in Cloud SQL will be lost.

```bash
# 1. Delete the Cloud Run service
gcloud run services delete any-booking \
  --region=us-central1 --quiet

# 2. Delete Cloud Run jobs (if created during first deploy)
gcloud run jobs delete import-halls   --region=us-central1 --quiet 2>/dev/null || true
gcloud run jobs delete seed-sample-data --region=us-central1 --quiet 2>/dev/null || true

# 3. Delete the Cloud SQL instance (drops all databases and users inside it)
gcloud sql instances delete any-booking-db --quiet

# 4. Delete all Secret Manager secrets
for secret in \
  DJANGO_SECRET_KEY DATABASE_URL \
  RAZORPAY_KEY_ID RAZORPAY_KEY_SECRET \
  EMAIL_HOST EMAIL_HOST_USER EMAIL_HOST_PASSWORD \
  DEFAULT_FROM_EMAIL ADMIN_NOTIFY_EMAIL SITE_URL EMAIL_BACKEND; do
  gcloud secrets delete "$secret" --quiet 2>/dev/null || true
done

# 5. Delete all images in Artifact Registry (then the repository itself)
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/YOUR_PROJECT_ID/any-booking-repo \
  --format="value(IMAGE)" \
  | xargs -I{} gcloud artifacts docker images delete {} --quiet 2>/dev/null || true

gcloud artifacts repositories delete any-booking-repo \
  --location=us-central1 --quiet

# 6. Remove IAM bindings from the service account
SA_EMAIL="github-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com"

for role in \
  roles/run.admin \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor \
  roles/cloudsql.client \
  roles/iam.serviceAccountUser; do
  gcloud projects remove-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$role" --quiet 2>/dev/null || true
done

# 7. Delete the Workload Identity pool provider and pool
gcloud iam workload-identity-pools providers delete github-provider \
  --location=global \
  --workload-identity-pool=github-pool --quiet

gcloud iam workload-identity-pools delete github-pool \
  --location=global --quiet

# 8. Delete the service account
gcloud iam service-accounts delete "$SA_EMAIL" --quiet
```

> **Tip:** To tear down only the app (keeping infra intact for a redeploy), delete only the Cloud Run service (step 1) and skip the rest.

---

## Connecting to the Production Database Locally

Useful for debugging or running one-off queries against Cloud SQL.

```bash
# 1. Install psql (macOS)
brew install libpq
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 2. Set up Application Default Credentials
gcloud auth application-default login

# 3. Connect
gcloud sql connect any-booking-db \
  --user=anybooking_user \
  --database=anybooking
```

Type `\q` to exit the psql prompt.

---

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL 14+

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
Copy `.env.example` to `.env` and fill in your values:
```
DEBUG=True
SECRET_KEY=<generate a strong key>
DATABASE_URL=postgres://<user>:<password>@localhost:5432/anybooking
ALLOWED_HOSTS=localhost,127.0.0.1

# Razorpay — only required if India payments are enabled in Admin → Payment Gateway Configs
RAZORPAY_KEY_ID=<your Razorpay key>
RAZORPAY_KEY_SECRET=<your Razorpay secret>
```

### 3. Create the database
```bash
createdb anybooking
```

### 4. Run migrations
```bash
python manage.py migrate
```

### 5. Create admin superuser
```bash
python manage.py createsuperuser
```

### 6. Import banquet hall data from Excel
```bash
python manage.py import_halls "/path/to/Banquet Halls.xlsx"
```
This will:
- Create India → Telangana → Districts → Cities location hierarchy
- Create all 7 service categories (if not yet added via admin)
- Create attribute definitions (AC Hall, Non-AC, Capacity, Rooms)
- Create a country-level RegionalCategoryConfig for India/Banquet Hall
- Import all hall listings as Services with attribute values

To re-import cleanly:
```bash
python manage.py import_halls "path/to/file.xlsx" --clear
```

### 7. (Optional) Seed sample data
Seeds USA, Canada, UAE location hierarchies and ~37 sample services across all non-hall categories. Also seeds 16 admin log entries so the dashboard audit log is populated.
```bash
python manage.py seed_sample_data
```

### 8. Collect static files (production)
```bash
python manage.py collectstatic
```

### 9. Run the development server
```bash
python manage.py runserver
```

Visit:

| URL | Description |
|---|---|
| http://127.0.0.1:8000/ | Public site |
| http://127.0.0.1:8000/admin/ | Admin portal |
| http://127.0.0.1:8000/admin/dashboard/ | Admin dashboard |
| http://127.0.0.1:8000/vendor/login/ | Vendor portal login |

---

## Admin Dashboard

The dashboard is accessible at `/admin/dashboard/` and is also linked from the **📊 Dashboard** button in the top-right corner of every admin page.

### What it shows

| Section | Details |
|---|---|
| **Stat cards** | Total / Confirmed / Completed / Cancelled bookings; Total order value; Advance collected; Balance outstanding; Payments captured (Razorpay); Refunded amount; Active services |
| **Bookings trend** | Line chart — daily count for the last 30 days |
| **Revenue trend** | Bar chart — total value vs advance collected per month (last 6 months) |
| **Status doughnut** | Pending / Confirmed / Completed / Cancelled breakdown |
| **Top services** | Ranked by booking count with confirmed count |
| **Upcoming events** | Next 10 confirmed bookings sorted by event date |
| **Recent bookings** | Last 15 bookings with status badges and amounts |
| **Audit log** | Last 20 admin actions (Added / Changed / Deleted) with user, object, and timestamp |

### Location scoping
Superusers see all data across all regions. Staff users with a **StaffProfile** see only data for their assigned country, state, or city. The active scope is shown as a badge ("📍 Telangana, India") in the dashboard header.

---

## Location-Scoped Staff

Admin users can be restricted to a specific country, state, or city. Scoping is enforced across Services, Vendors, Bookings, Blocked Dates, Payments, and the Dashboard.

### Access levels

| User type | Access |
|---|---|
| **Superuser** | All data, all admin sections (Users, Groups, Staff Profiles) |
| **Staff — City scope** | Only records for that city |
| **Staff — State scope** | Only records for any city in that state |
| **Staff — Country scope** | Only records for any city in that country |
| **Staff — no profile** | Nothing (fail-safe: empty querysets) |

Non-superuser staff cannot see the Users or Groups sections of the admin.

### Creating a location-scoped staff user

1. Go to **Admin → Users → Add User**, set `is_staff = True`
2. Go to **Admin → Staff Profiles → Add**
3. Select the User and set `Country`, `State`, or `City` — most specific wins
4. Save — the user can now log in and will see only their region's data

### Creating a test staff user (local dev)
```python
python manage.py shell -c "
from django.contrib.auth.models import User
from services.models import StaffProfile, Country, State

u = User.objects.create_user('staff_tg', password='testpass123', is_staff=True)
state = State.objects.get(name='Telangana')
country = Country.objects.get(name='India')
StaffProfile.objects.create(user=u, country=country, state=state)
print('Created:', u.username)
"
```

---

## Vendor Portal

Vendors log in at `/vendor/login/` and see only their own listings and bookings — no admin access required.

### Access levels

| User type | Access |
|---|---|
| **Superuser / Staff** | Full Django admin (`/admin/`) |
| **Vendor user** | Vendor portal only (`/vendor/`) — own listings and bookings |

### Creating a vendor login account

**From the admin (recommended):**

1. Go to **Admin → Vendors → [vendor name]**
2. Scroll to the **Portal Access** fieldset — click **Create login account for this vendor**
3. Enter a username and password, click **Create account**
4. The new user is automatically linked to the vendor and added to the **Vendor** Django group

**Manually:**

1. Go to **Admin → Users → Add User**, set a username and password
2. Under **Groups**, add the user to the **Vendor** group (`is_staff` and `is_superuser` must remain unticked)
3. Go to **Admin → Vendors → [vendor name]**, set the **User** field to the new user, save

### What vendor users can see

| Page | URL | Contents |
|---|---|---|
| Dashboard | `/vendor/dashboard/` | Stat cards (total/pending/confirmed/completed bookings), active listings, recent bookings |
| Bookings | `/vendor/bookings/` | All bookings for their services; filterable by service and status |

Vendors cannot see other vendors' data, access the Django admin, or modify any records — the portal is read-only.

### No extra environment variables

The vendor portal requires no additional secrets or environment variables. It uses the same Django session auth as the admin.

---

## Category Management

All 7 service categories are pre-defined. Each can be enabled or disabled independently from **Admin → Categories**.

### Enabling / disabling a category

1. Go to **Admin → Categories**
2. Tick or untick the **Is Active** checkbox in the list (inline-editable)
3. Click **Save** — the change takes effect immediately on the public site

Disabled categories are hidden from:
- The navbar
- The Browse by Category section on the home page
- The category sidebar on the service list page
- Category detail URLs (returns 404)

By default, only **Banquet Hall** is active. Enable additional categories as the business expands to them.

### Adding attributes for a category

Go to **Admin → Attribute Definitions → Add**:

| Category | Example attributes |
|---|---|
| Banquet Hall | AC Hall, Non-AC Hall, Venue Capacity, Lunch Capacity, AC Rooms, Non-AC Rooms |
| Hotels | AC Rooms, Non-AC Rooms, Swimming Pool, Gym, Restaurant |
| Catering | Veg, Non-Veg, Jain Food, Min Guests, Price Per Plate |
| Music Band | Genre, No. of Artists, Sound Equipment |
| Dancing | Style, Group/Solo, Duration |
| Priests | Religion, Ceremony Type, Language |
| Event Management | Wedding, Corporate, Birthday, Decoration, Photography |

---

## Adding a New Country/Region

1. Go to **Admin → Countries → Add Country** (set name, ISO code, currency symbol, phone code)
2. Add **States** under that country
3. Add **Districts** and **Cities** under each state
4. Go to **Admin → Regional Category Configs → Add**
   - Pick the Category (e.g. Banquet Hall) and Country (and optionally a State for a state-level override)
   - Tick the **Enabled Attributes** that apply in that region
   - Set a local **Price Unit Label** (e.g. "per night", "per plate")
   - Optionally set a **Local Display Name** if the category is known by a different name in that region

State-level configs override country-level configs automatically.

---

## How Regional Label Overrides Work

Category names and attribute labels can be customised per country or state so users always see terminology natural to their region — for example **"Priests"** becomes **"Purohit"** in Telangana or **"Archakar"** in Tamil Nadu.

### Priority order
```
State-level label  →  Country-level label  →  Default English name
```
The most specific match always wins.

### What can be overridden

| What | Model | Scope |
|---|---|---|
| Category display name | `RegionalCategoryConfig.local_display_name` | Country or State |
| Category description | `RegionalCategoryConfig.local_description` | Country or State |
| Attribute label | `AttributeLocalName.local_name` | Country or State |
| Price unit label | `RegionalCategoryConfig.price_unit_label` | Country or State |
| Which attributes are shown | `RegionalCategoryConfig.enabled_attributes` | Country or State |

### Where the label appears automatically
Once configured, the local name shows throughout the UI whenever the user has that region selected:
- Navbar category links
- Home page category cards
- List page heading, breadcrumb, and sidebar category links
- Service card category badge
- Service detail page breadcrumb and category badge
- Feature/attribute labels inside service cards and detail pages

### Setting a category label override

1. Go to **Admin → Regional Category Configs → Add**
2. Set **Category**, **Country**, and optionally **State**
3. Fill in **Local Display Name** and optionally **Local Description**
4. Save — takes effect immediately

| Region | Category | Local Name |
|---|---|---|
| India (default) | Priests | Pandit / Priest |
| Telangana | Priests | Purohit |
| Tamil Nadu | Priests | Archakar |
| Punjab | Priests | Granthi |

### Setting an attribute label override

1. Go to **Admin → Attribute Definitions → select the attribute**
2. Scroll to the **Attribute Local Names** inline section
3. Add a row: Country + optional State + Local Name
4. Save

---

## Location Preference (Public Site)

On first visit, users see a modal to set their preferred country and state. The preference is saved in cookies (`ab_country`, `ab_state`) for one year and is used to:
- Pre-filter the service list
- Pre-populate location dropdowns
- Show location-filtered counts on category cards
- Display the current location in the navbar ("📍 Telangana, India")

Users can change their location at any time via the **Change** link in the navbar. The modal also offers **Auto-detect** which uses the IP geolocation API (`ipapi.co`) to suggest a matching country and state from the database.

---

## Service Ratings & Review Moderation

All customer reviews are held in a **pending** state until an admin approves or rejects them. No review is visible on the public site until explicitly approved.

### Moderation workflow

1. Go to **Admin → Reviews → Reviews**
2. Use the **Status** filter in the right sidebar to show `Pending` reviews
3. Select one or more reviews
4. Choose an action from the dropdown:
   - **Approve selected reviews** — makes them visible immediately on the service detail page and updates the average star rating on listing cards
   - **Reject selected reviews** — hides them permanently; the record is kept for audit purposes
5. Click **Go**

Review content (reviewer name, rating, body, submission date) is read-only — it cannot be edited from the admin. Only the status can be changed.

### No environment variables required

Review moderation is fully configuration-driven. No `.env` changes needed.

---

## Photo / Image Management

### Service listing photos

Each service can have multiple photos. The first one marked **Primary** is used as the card thumbnail on the listing page.

1. Go to **Admin → Services → [service name]**
2. Scroll to the **Images** inline section at the bottom
3. Click **Add another Image**, upload a file, and tick **Is Primary** for the main photo
4. Add more rows for additional photos — drag to reorder by **Order** field
5. Save

Images appear in the photo gallery on the service detail page. The primary image is also shown on listing cards.

### Category tiles (home page)

1. Go to **Admin → Categories → [category name]**
2. Upload an image to the **Image** field
3. Save — the image appears in the "Browse by Category" grid on the home page

If no image is set, the tile falls back to the category's Bootstrap icon on a coloured background.

### Featured city cards (home page)

1. Go to **Admin → Cities → [city name]**
2. Upload an image to the **Image** field
3. Tick **Is Featured** so the city appears in the "Explore Cities" row on the home page
4. Save

Up to 6 featured cities are shown.

### Production note — images on Cloud Run

Cloud Run containers have no persistent disk. Media files are automatically stored in Google Cloud Storage (`gs://${PROJECT_ID}-media`) via `django-storages`. The `GCS_MEDIA_BUCKET` secret is mounted on every deploy — no extra setup needed.

If setting up a new environment, create the bucket and grant access once:

```bash
gsutil mb -l us-central1 gs://${PROJECT_ID}-media

PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

printf '%s' "${PROJECT_ID}-media" | gcloud secrets create GCS_MEDIA_BUCKET --data-file=-
```

---

## Admin Bulk Actions

### Services (Admin → Services)
| Action | Effect |
|---|---|
| ⭐ Mark selected as Featured | Sets `is_featured = True` |
| Remove Featured | Sets `is_featured = False` |
| ✅ Activate | Sets `is_active = True` |
| 🚫 Deactivate | Sets `is_active = False` |

### Reviews (Admin → Reviews)
| Action | Effect |
|---|---|
| ✅ Approve selected reviews | Sets status → Approved; review appears publicly |
| ❌ Reject selected reviews | Sets status → Rejected; review hidden permanently |

### Bookings (Admin → Bookings)
| Action | Effect |
|---|---|
| ✅ Approve & notify customer | Status → Confirmed; sends approval email to customer |
| ❌ Cancel with refund & notify customer | Opens refund form; status → Cancelled; sends cancellation email |
| 🏁 Mark as Completed | Status → Completed (Confirmed only) |

### Blocked Dates (Admin → Blocked Dates)
| Action | Effect |
|---|---|
| 🗑 Remove selected blocked dates | Deletes the selected blocked date records |

---

## Email Workflow

### How it works

All transactional emails are sent via Django's email backend. In development they print to the console; in production configure SMTP via environment variables.

Every email sent (or failed) is recorded in the **EmailLog** table and viewable at **Admin → Bookings → Email Logs**.

### Email triggers

| Event | Recipient(s) | Template |
|---|---|---|
| Customer submits booking | Customer | `booking_received.html` |
| Customer submits booking | Super-admin + area admins | `admin_notify.html` |
| Admin approves booking | Customer | `booking_approved.html` |
| Admin cancels booking | Customer | `booking_cancelled.html` |

**Area admin resolution:** when a booking arrives, the system queries `StaffProfile` records whose city, state, or country scope covers the booking's location and emails every matching staff user.

### Cancel with Refund workflow

1. In **Admin → Bookings**, select one or more bookings
2. Choose **❌ Cancel with refund & notify customer** from the Actions dropdown
3. An intermediate form appears — fill in:
   - **Refund Type**: Full Refund / Partial Refund / No Refund
   - **Refund Amount** (if Partial): the exact amount to be returned
   - **Cancellation Reason**: shown verbatim to the customer in the email
   - **Internal Notes**: optional, admin-only, not sent to the customer
4. Click **Cancel Bookings & Send Emails** — bookings are cancelled and emails fire immediately

### Email Logs

Go to **Admin → Bookings → Email Logs** to see every email sent, with:
- Type badge (colour-coded: blue = received, amber = admin notify, green = approved, red = cancelled)
- Recipient address and linked booking
- Subject line and full HTML body preview
- Sent / Failed status
- Timestamp and which admin triggered it (system = auto-sent on booking creation)

The **Booking change view** also shows a compact email history table under the collapsible *Email Communications* section.

### Local development

In development (`EMAIL_BACKEND=console`) emails are printed to the terminal — no SMTP setup needed. To test real delivery locally, use [Mailpit](https://mailpit.axllent.org/) or a Gmail App Password:

```bash
# .env additions for local SMTP testing
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=xxxx-xxxx-xxxx-xxxx   # Gmail App Password
DEFAULT_FROM_EMAIL=AnyBooking <noreply@anybooking.in>
ADMIN_NOTIFY_EMAIL=your@gmail.com
SITE_URL=http://127.0.0.1:8000
```

### Production (Google Secret Manager)

Store each email setting as a separate secret (see GCP setup step 6) and mount them as environment variables in your Cloud Run service. The `EMAIL_BACKEND` secret should be set to:
```
django.core.mail.backends.smtp.EmailBackend
```

All email secrets are auto-mounted on every deploy via the CI/CD pipeline — no manual `gcloud run services update` step needed.

---

## Payment Gateway

Online payments are **feature-flagged per country** via `PaymentGatewayConfig`. When a country has `is_enabled=False` (the default), bookings skip payment entirely. When enabled, customers are redirected to the configured gateway immediately after booking submission.

### Enabling payments for India (Razorpay)

#### 1. Add API credentials to `.env` (local) or Secret Manager (production)

**Local `.env`:**
```
RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXX
RAZORPAY_KEY_SECRET=your_razorpay_secret
```

**Production — store in Secret Manager and mount on Cloud Run:**
```bash
echo -n "rzp_live_XXXXXXXXXXXX" | gcloud secrets create RAZORPAY_KEY_ID --data-file=-
echo -n "your_live_secret"      | gcloud secrets create RAZORPAY_KEY_SECRET --data-file=-

gcloud run services update any-booking \
  --region=us-central1 \
  --update-secrets=\
RAZORPAY_KEY_ID=RAZORPAY_KEY_ID:latest,\
RAZORPAY_KEY_SECRET=RAZORPAY_KEY_SECRET:latest
```

Get your keys from the [Razorpay Dashboard → Settings → API Keys](https://dashboard.razorpay.com/app/website-app-settings/api-keys). Use **Test** keys for dev, **Live** keys for production.

#### 2. Enable the gateway in Admin

1. Go to **Admin → Payment Gateway Configs → Add**
2. Select **Country: India**, **Gateway: Razorpay**, tick **Is Enabled**
3. Optionally set a **Display Name** (e.g. "Pay Online")
4. Save — bookings for services in Indian cities now redirect to Razorpay checkout

#### 3. Configure the Razorpay webhook (production)

In your Razorpay Dashboard → Webhooks, add:
```
https://your-domain.com/payments/callback/
```
Events: `payment.captured`, `payment.failed`. The callback endpoint uses HMAC-SHA256 to verify every payload.

### How the gateway selection works

```
booking_create  →  get_gateway_for_country(country)
                        ├── No PaymentGatewayConfig? → skip payment
                        ├── is_enabled=False?        → skip payment
                        └── is_enabled=True          → redirect to initiate_payment
                                                          └── gateway.create_order()
                                                          └── render checkout_<slug>.html
payment_callback  →  match gateway from POST data → gateway.verify_callback()
                        ├── valid   → Payment.status = captured → Booking.status = confirmed
                        └── invalid → Payment.status = failed → show failed.html
```

### Adding a new gateway (e.g. Stripe for UK)

1. Create `payments/gateways/stripe_gateway.py` implementing `BasePaymentGateway`:
   - `create_order(booking)` → create a Stripe PaymentIntent, return `{order_id, amount, currency}`
   - `verify_callback(post_data)` → verify Stripe webhook signature
   - `get_checkout_context(booking, payment)` → return vars needed by the template
   - `extract_order_id(post_data)` → pull the intent ID from POST data
2. Register it in `payments/gateways/registry.py`:
   ```python
   from .stripe_gateway import StripeGateway
   GATEWAY_REGISTRY['stripe'] = StripeGateway
   ```
3. Create `templates/payments/checkout_stripe.html`
4. Store `STRIPE_PUBLISHABLE_KEY` / `STRIPE_SECRET_KEY` in `.env` / Secret Manager
5. In Admin → Payment Gateway Configs, add a row for UK with gateway=Stripe, `is_enabled=True`

No changes to `bookings/views.py` or `payments/views.py` are needed.

---

## Terms of Use

Terms of Use are **feature-flagged per document** via the `is_active` field. When no active terms apply to a service, the booking form shows no acceptance step and nothing changes for the customer.

### Creating terms

1. Go to **Admin → Terms of Use → Add**
2. Fill in **Title**, **Version** (e.g. `v1.0` or `2024-01`), and **Content** (HTML supported)
3. Set **Scope**:
   - **Site-wide** — shown on every booking regardless of service
   - **Service-specific** — select a specific service; shown only for bookings of that service
4. Tick **Is Active**
5. Save — the terms box appears on the booking form immediately

Multiple active terms (site-wide + service-specific) stack: all are shown together, with one combined checkbox.

### Updating terms

Create a **new** `TermsOfUse` record with a new version string rather than editing the existing one. Deactivate the old record by unticking `Is Active`. This preserves the original text for all historical acceptances.

### Viewing acceptance records

| Location | What you see |
|---|---|
| **Admin → Terms → Terms Acceptances** | All acceptances across all bookings; searchable by customer name, email, IP address; filterable by terms document and date |
| **Admin → Bookings → [booking detail]** | Terms Acceptances inline — shows which documents were accepted for that booking, the version, IP, and timestamp |
| **Admin → Terms of Use → [terms detail]** | Acceptances inline — shows every booking that accepted this specific document |

Each acceptance record captures:
- The exact version string at the moment of signing (snapshot)
- Customer IP address (handles `X-Forwarded-For` proxy headers)
- User agent string
- Timestamp (UTC)

Acceptance records are **immutable** — they cannot be edited or deleted via the admin. Terms documents that have existing acceptances are also protected from deletion.

### Disabling terms

Untick **Is Active** on the terms document. Existing acceptance records are preserved. The booking form immediately stops showing that document.

### No environment variables required

Terms of Use is fully configuration-driven via the admin. No `.env` changes, no secrets, no deploy needed.

---

## Booking Lookup & Confirmation Numbers

### How confirmation numbers work

Every booking gets a unique `AB-XXXXXXXX` code on creation (8 random unambiguous characters). It is:
- Shown prominently on the post-booking confirmation page
- Included in the subject line and body of all transactional emails
- Searchable in the admin (Admin → Bookings search box)

No setup is required — confirmation numbers are generated automatically.

### Find My Booking page (`/bookings/find/`)

Accessible from the navbar. Customers can search by:
- **Confirmation number** — the `AB-XXXXXXXX` code from their email
- **Last name + phone number** — both fields required; partial match on each

Only **pending** and **confirmed** bookings are returned. Cancelled and completed bookings are intentionally excluded.

No configuration needed. The page is always live.

---

## Customer Cancellation Requests

### Workflow overview

```
Customer finds booking (/bookings/find/)
  └── Clicks "Request Cancellation"
        └── Submits reason (/bookings/cancel-request/<conf_num>/)
              ├── Customer receives acknowledgement email
              ├── Admin(s) receive alert email with "Review in Admin" button
              └── Booking flagged: cancellation_requested = True

Admin reviews:
  └── Admin → Bookings → filter "Cancellation Requested = Yes"
        └── Selects booking → "❌ Cancel with refund & notify customer" action
              └── Fills refund form → booking cancelled → customer notified
```

### Admin actions

| Location | What to do |
|---|---|
| **Admin → Bookings list** | Filter by **Cancellation Requested = Yes** to see all pending requests; look for the **⚠ Requested** amber badge |
| **Booking detail** | Expand **Customer Cancellation Request** fieldset to read the reason and timestamp |
| **Booking list** | Select the booking → **❌ Cancel with refund & notify customer** → fill in refund details and confirm |

### Notes

- Customers can only submit one request per booking — the form blocks duplicates
- The cancellation request does **not** automatically cancel the booking; admin controls the refund decision
- All emails (customer acknowledgement + admin alert) are recorded in Email Logs
- No environment variables or configuration required beyond the SMTP settings already in place

---

## Vendor Booking Notifications

Vendor email notifications are **off by default** and require no code changes or environment variables to enable. They are controlled entirely from the admin.

### Enabling for a vendor

1. Go to **Admin → Vendors → [vendor name]**
2. Set the **Email** field to the vendor's email address (if not already set)
3. Tick **Notify on Booking** under the *Booking Notifications* fieldset
4. Save

You can also bulk-toggle the flag from the **Admin → Vendors list** — `Notify on Booking` is an inline-editable column.

### What triggers a vendor email

| Trigger | Email sent |
|---|---|
| Admin runs **✅ Approve & notify customer** | Vendor receives booking confirmation with full customer details |
| Admin runs **❌ Cancel with refund & notify customer** | Vendor receives cancellation notice with the reason and freed date |

The vendor email fires **in addition to** the customer email — both are sent in the same admin action. No extra steps required.

### Guard conditions

A vendor email is only sent when **both** conditions are true:
- `Vendor.notify_on_booking = True`
- `Vendor.email` is a non-empty valid address

If either is missing the send is silently skipped and no EmailLog entry is created for the vendor.

### Viewing vendor emails in the audit log

Go to **Admin → Bookings → Email Logs** and filter by type:
- **Booking Confirmed (vendor)** — green badge
- **Booking Cancelled (vendor)** — rose badge

Both are linked to the relevant booking and show the full rendered email body.
