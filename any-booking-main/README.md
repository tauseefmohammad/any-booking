# AnyBooking

A multi-region event booking platform for **Banquet Halls, Music Bands, Catering, Hotels, Dancing, Priests, and Event Management** — built with Django, PostgreSQL, and deployed to Google Cloud Run.

---

## Features

- **7 service categories** — each with configurable attributes (AC/Non-AC, capacity, veg/non-veg, etc.)
- **Photo-forward home page** — full-width hero, category photo tiles, featured city cards, and a benefits strip; images managed entirely from the admin with no code changes
- **Location hierarchy** — Country → State → District → City with cascading dropdowns
- **Regional label overrides** — category and attribute names adapt to the local language (e.g. *Priests* → *Purohit* in Telangana)
- **Availability calendar** — real-time date picker blocks already-booked and admin-blocked dates
- **Booking flow** — customer details form, event date, guest count, special requests
- **Service ratings & reviews** — customers submit star ratings and review text on the service detail page; all submissions go into an admin moderation queue before publishing; approved reviews show on the detail page and the average star rating appears on listing cards
- **Country-based payment gateways** — feature-flagged per country; Razorpay live for India; add new gateways without touching existing code
- **Terms of Use** — feature-flagged per site and/or per service; customers must read and accept before booking; full immutable acceptance audit trail (IP, user agent, version)
- **Admin portal** — full Django admin for vendors, services, bookings, payments, regional config, and review moderation
- **Admin dashboard** — live summary of bookings, revenue, refunds, and audit log with Chart.js charts
- **Location-scoped staff** — admin users restricted to a country/state/city; superuser sees everything
- **Email workflow** — automated emails on booking submission, approval, and cancellation; full HTML templates; every email audited in Email Logs
- **Approve / Cancel with refund** — admin actions to confirm or cancel bookings with full/partial/no refund selection; customer notified by email in each case
- **Vendor booking notifications** — feature-flagged per vendor; when enabled, the service provider receives an email on confirmation and cancellation
- **Booking lookup** — customers find active bookings by confirmation number or last name + phone at `/bookings/find/`
- **Customer cancellation requests** — customers request cancellation with a reason; admin is alerted; admin processes refund via existing Cancel+Refund action
- **Excel import** — bulk-load hall listings from `.xlsx` via management command

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2, Python 3.11 |
| Database | PostgreSQL 16 (Cloud SQL in production, SQLite in dev) |
| Frontend | Bootstrap 5, Bootstrap Icons, vanilla JS |
| Payments | Razorpay (India) · extensible gateway layer |
| Static files | WhiteNoise |
| Container | Docker |
| CI/CD | GitHub Actions |
| Hosting | Google Cloud Run |
| Image registry | Google Artifact Registry |

---

## Project Structure

```
any-booking/
├── services/           # Categories, attributes, vendors, listings, location hierarchy
│   ├── models.py       # Country, State, District, City, Category, Service, StaffProfile, …
│   ├── views.py        # Home, list (with location filters), detail, AJAX dropdowns
│   ├── admin.py        # Full admin with bulk actions, staff user management
│   ├── admin_mixins.py # LocationRestrictedMixin — scopes querysets by staff location
│   ├── dashboard.py    # Admin dashboard view (bookings, revenue, audit log)
│   ├── context_processors.py  # Injects location preference into every template
│   ├── templatetags/   # local_names — resolves region-aware display names
│   └── management/
│       └── commands/
│           ├── import_halls.py     # Bulk Excel import
│           └── seed_sample_data.py # Seeds all 7 categories + USA/Canada/UAE locations
├── reviews/            # Service ratings and review moderation
│   ├── models.py       # Review (rating 1-5, body, reviewer_name, status, created_at)
│   ├── forms.py        # ReviewForm — reviewer_name, rating, body
│   ├── views.py        # add_review — POST only, sets status=pending, redirects
│   ├── urls.py         # /services/<slug>/reviews/add/
│   ├── admin.py        # ReviewAdmin — bulk approve/reject actions, readonly content
│   └── migrations/
├── bookings/           # Booking model, availability check, booking form, email workflow
│   ├── models.py       # Booking (+ refund fields), BlockedDate, EmailLog
│   ├── emails.py       # send_booking_received/approved/cancelled + admin recipient resolution
│   ├── signals.py      # post_save → send_booking_received on creation
│   └── admin.py        # Approve action, Cancel+Refund form, EmailLog admin
├── terms/              # Terms of Use — feature-flagged per site / per service
│   ├── models.py       # TermsOfUse (content + is_active flag), TermsAcceptance (immutable audit)
│   ├── admin.py        # TermsOfUseAdmin (preview, acceptance count, delete guard), TermsAcceptanceAdmin
│   └── migrations/
├── payments/           # Country-based payment gateway layer
│   ├── models.py       # Payment, PaymentGatewayConfig (per-country feature flag)
│   ├── views.py        # initiate_payment + payment_callback (gateway-agnostic)
│   ├── admin.py        # Payment admin with gateway/status badges; PaymentGatewayConfig admin
│   └── gateways/
│       ├── base.py              # BasePaymentGateway contract + GatewayError
│       ├── razorpay_gateway.py  # Razorpay implementation (HMAC-SHA256 verification)
│       └── registry.py          # GATEWAY_REGISTRY + get_gateway_for_country()
├── templates/
│   ├── admin/
│   │   ├── base_site.html          # Injects 📊 Dashboard button into every admin page
│   │   ├── dashboard.html          # Dashboard template with Chart.js charts
│   │   └── bookings/
│   │       └── cancel_refund_form.html  # Intermediate form for Cancel+Refund action
│   ├── emails/
│   │   ├── _base.html              # Shared HTML email layout
│   │   ├── booking_received.html   # Customer: booking submitted
│   │   ├── admin_notify.html       # Admin: new booking alert
│   │   ├── booking_approved.html   # Customer: booking confirmed
│   │   └── booking_cancelled.html  # Customer: cancellation + refund details
│   └── …               # Bootstrap 5 templates (base, home, list, detail, booking, payment)
├── static/css/         # Custom styles
├── config/             # Django settings, URLs, WSGI
├── Dockerfile
├── .github/workflows/
│   └── deploy.yml      # CI/CD: Test → Build → Deploy to Cloud Run
├── DB_SCHEMA.md        # Full database schema reference
└── SETUP.md            # Local dev + GCP deployment guide
```

---

## Data Model (summary)

```
Country → State → District → City
                                └── Vendor → Service → ServiceAttributeValue
                                                └── Booking → Payment
                                                │       └── EmailLog  (audit of all comms)
                                                ├── TermsAcceptance  (immutable sign-off record)
                                                └── Review  (rating 1-5, body, moderation status)
Category → AttributeDefinition → AttributeLocalName   (regional label overrides)
Category × Country × State → RegionalCategoryConfig   (local name, enabled attrs, price unit)
StaffProfile → User  (location scope: country / state / city)
Country → PaymentGatewayConfig  (gateway slug + is_enabled feature flag)
TermsOfUse  (site-wide or Service FK; is_active feature flag)
```

See [DB_SCHEMA.md](DB_SCHEMA.md) for the full table-by-table reference.

---

## Service Ratings & Reviews

Customers can rate and review services directly on the service detail page. All submissions go into a moderation queue — reviews are not published until an admin approves them.

### Customer experience

- Customers fill in their name, a star rating (1–5), and a written review on the service detail page
- After submitting they see a flash message: "Thanks! Your review is awaiting approval."
- Approved reviews appear in chronological order under the service description
- The average star rating and review count are displayed as a badge on every listing card and at the top of the detail page

### Admin workflow

| Location | What to do |
|---|---|
| **Admin → Reviews → Reviews** | See all submissions with status, rating, and reviewer |
| **Admin → Reviews → filter by status: Pending** | Find all reviews awaiting moderation |
| **Select reviews → Approve selected reviews** | Publishes them immediately on the public site |
| **Select reviews → Reject selected reviews** | Hides them permanently; review content is preserved for audit |

Review content (name, rating, body, submitted date) is **read-only** in the admin — it cannot be edited after submission. Only the status can be changed.

### No environment variables required

Reviews are fully configuration-driven. No `.env` changes or gateway credentials needed.

---

## Regional Label Overrides

Category and attribute names can be customised per country or state so users always see terminology natural to their region.

| Region | Category | Shown as |
|---|---|---|
| (default) | Priests | Priests |
| India (country-wide) | Priests | Pandit / Priest |
| Telangana | Priests | Purohit |
| Tamil Nadu | Priests | Archakar |
| Punjab | Priests | Granthi |

**Priority:** State-level → Country-level → Default English name.

Configured via **Admin → Regional Category Configs**. See [SETUP.md](SETUP.md#how-regional-label-overrides-work) for full details.

---

## Admin Dashboard

A live summary dashboard is available at `/admin/dashboard/` and is linked from a **📊 Dashboard** button that appears in the top-right corner of every admin page.

| Section | Details |
|---|---|
| **Stat cards** | Total / Confirmed / Completed / Cancelled bookings; Total order value; Advance collected; Balance outstanding; Payments captured; Refunded amount |
| **Bookings trend** | Line chart — daily booking count for the last 30 days |
| **Revenue trend** | Bar chart — total value vs advance collected per month (last 6 months) |
| **Status doughnut** | Pending / Confirmed / Completed / Cancelled breakdown |
| **Top services** | Ranked by booking count with confirmed count |
| **Upcoming events** | Next 10 confirmed bookings sorted by event date |
| **Recent bookings** | Last 15 bookings with status badges and amounts |
| **Audit log** | Last 20 admin actions (Added / Changed / Deleted) with user, object, timestamp |

The dashboard is **location-aware** — staff users see only data for their assigned region.

---

## User Roles & Access

The platform has three distinct access tiers. Each uses a separate login and sees a different slice of the system.

### Access levels

| Role | Login URL | What they can access |
|---|---|---|
| **Superuser** | `/admin/` | All locations, all admin sections including Users, Groups, and Staff Profiles |
| **Staff — City scope** | `/admin/` | Only admin records belonging to that city |
| **Staff — State scope** | `/admin/` | Only admin records belonging to any city in that state |
| **Staff — Country scope** | `/admin/` | Only admin records belonging to any city in that country |
| **Staff — no profile** | `/admin/` | Nothing (fail-safe: empty querysets) |
| **Vendor** | `/vendor/login/` | Their own listings and bookings only — no admin access |

### Creating a location-scoped staff user

Staff users access the full Django admin but are restricted to their assigned region.

1. Go to **Admin → Users → Add User** — create the account with `is_staff = True`
2. Go to **Admin → Staff Profiles → Add**
3. Select the `User`, then set `Country`, `State`, or `City` — the most specific one wins
4. Save — the user can now log in and will see only their region's data

The **Users** and **Groups** sections of the admin are hidden from non-superusers entirely.

### Creating a vendor user

Vendor users access only the vendor portal (`/vendor/…`). They do **not** need `is_staff`.

1. Go to **Admin → Services → Vendors → [vendor]**
2. Scroll to **Portal Access → "Create new login account →"**
3. Enter a username and password, click **Create account**
4. Share the credentials — the vendor logs in at `/vendor/login/`

To link an existing Django user to a vendor instead, pick them from the **User** dropdown in the same fieldset.

### Django user flags summary

| Role | `is_active` | `is_staff` | `is_superuser` | Linked to |
|---|---|---|---|---|
| Superuser | ✓ | ✓ | ✓ | — |
| Staff | ✓ | ✓ | ✗ | `StaffProfile` |
| Vendor | ✓ | ✗ | ✗ | `Vendor.user` |

---

## Email Workflow

Every booking state change triggers an email. All emails are recorded in **EmailLog** regardless of success or failure.

### Automated emails

| Trigger | Recipients | Template |
|---|---|---|
| Customer submits a booking | Customer (confirmation) | `booking_received.html` |
| Customer submits a booking | Super-admin + all area admins covering that city | `admin_notify.html` |
| Admin approves a booking | Customer | `booking_approved.html` |
| Admin approves a booking | Vendor *(if notify_on_booking enabled)* | `vendor_booking_confirmed.html` |
| Admin cancels a booking | Customer (with refund details) | `booking_cancelled.html` |
| Admin cancels a booking | Vendor *(if notify_on_booking enabled)* | `vendor_booking_cancelled.html` |
| Customer requests cancellation | Customer (acknowledgement) | `cancellation_request_customer.html` |
| Customer requests cancellation | Super-admin + area admins | `cancellation_request_admin.html` |

**Area admin resolution** — on each new booking the system finds all `StaffProfile` users whose city, state, or country scope covers the booking's location and emails each of them.

**Vendor notification** — fires only when `Vendor.notify_on_booking = True` and the vendor has a valid email address. Controlled per vendor in Admin → Vendors.

### Admin actions

| Action | What it does |
|---|---|
| **✅ Approve & notify customer** | Sets status → Confirmed; sends approval email to customer; sends confirmation to vendor if enabled |
| **❌ Cancel with refund & notify customer** | Opens a form to select Full / Partial / No Refund, enter refund amount, cancellation reason (shown to customer), and internal notes; then cancels and emails customer and vendor |

### Email Logs (Admin → Bookings → Email Logs)

Every email is stored with: type badge, recipient, linked booking, subject, HTML body preview, sent/failed status, timestamp, and the admin user who triggered it. Filterable by email type, status, and date range.

The **Booking detail page** also shows an inline email history table under the *Email Communications* section.

### Email configuration

| Setting | Dev default | Production value |
|---|---|---|
| `EMAIL_BACKEND` | `console` (prints to terminal) | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | `smtp.gmail.com` | Your SMTP host |
| `EMAIL_PORT` | `587` | `587` (TLS) |
| `EMAIL_HOST_USER` | _(empty)_ | Your SMTP username |
| `EMAIL_HOST_PASSWORD` | _(empty)_ | App password / secret |
| `DEFAULT_FROM_EMAIL` | `AnyBooking <noreply@anybooking.in>` | Your from address |
| `ADMIN_NOTIFY_EMAIL` | _(empty)_ | Super-admin inbox |
| `SITE_URL` | `http://127.0.0.1:8000` | `https://your-domain.com` |

Set these in `.env` locally or in Google Secret Manager for production.

---

## Terms of Use

Terms can be required at booking time and are **feature-flagged per document** — enabling or disabling a terms document takes effect immediately without a deploy.

### Scope

| Scope | Shown when |
|---|---|
| **Site-wide** | Every booking, regardless of service |
| **Service-specific** | Only bookings for the chosen service |

Both can be active at the same time. The customer sees all applicable documents in a scrollable box and must tick a single "I have read and agree" checkbox before submitting.

### Acceptance audit trail

Every acceptance is saved as an immutable `TermsAcceptance` record containing:
- Linked booking and terms document
- Version string at the moment of signing (snapshot, unaffected by later edits)
- Customer IP address and user agent
- Timestamp

Accepted terms documents cannot be deleted from the admin (the record is protected).

### Admin

| Location | Purpose |
|---|---|
| **Admin → Terms of Use** | Create / edit terms; toggle Is Active; see acceptance count and rendered preview |
| **Admin → Terms → Terms Acceptances** | Full read-only log; searchable by customer name, email, IP |
| **Admin → Bookings → [booking detail]** | Terms Acceptances inline — see which documents were signed for each booking |

---

## Vendor Portal

Hall owners and service providers can log in to a dedicated portal to view their own listings and bookings — without access to the full admin.

### Vendor login

| URL | Description |
|---|---|
| `/vendor/login/` | Vendor sign-in page |
| `/vendor/dashboard/` | Overview — active listings, pending/confirmed booking counts, recent bookings |
| `/vendor/bookings/` | Full booking list with filter by service and status |

Vendors see **only their own data**. No cross-vendor information is accessible.

### Setting up a vendor account (admin)

1. Go to **Admin → Services → Vendors → [vendor]**
2. Scroll to the **Portal Access** section
3. Click **"Create new login account →"**
4. Enter a username and password, click **Create account**
5. Share the credentials with the vendor — they log in at `/vendor/login/`

To link an existing Django user instead, pick them from the **User** dropdown in the same section.

### What vendors can see

| Section | Details |
|---|---|
| **Dashboard** | Active listing count, pending and confirmed booking counts, last 10 bookings |
| **Bookings** | All bookings for their services — filterable by service and status; shows customer name, phone, email, event date, guest count, total amount, and status |

Vendors have read-only access. They cannot modify listings, approve bookings, or see other vendors' data.

---

## Vendor Booking Notifications

Service providers (vendors) can receive email notifications when bookings for their services are confirmed or cancelled. This is **feature-flagged per vendor** — off by default, enabled individually.

### Enabling for a vendor

1. Go to **Admin → Vendors → [vendor]**
2. Ensure the **Email** field is set to a valid address
3. Tick **Notify on Booking** (or toggle it inline from the vendor list)
4. Save — takes effect immediately for the next booking event

### What the vendor receives

| Event | Email includes |
|---|---|
| **Booking confirmed** | Customer name, phone, email; event date and time; guest count; special requests; advance paid and balance due; AnyBooking reference |
| **Booking cancelled** | Event date freed; cancellation reason; no further action required message |

Both emails are recorded in Email Logs with colour-coded type badges.

---

## Booking Lookup

Customers can find their own bookings without an account at **`/bookings/find/`** — linked from the navbar and from the post-booking confirmation page.

Only **pending** and **confirmed** bookings are returned. Cancelled and completed bookings are not shown.

### Search methods

| Method | Fields required |
|---|---|
| Confirmation number | The `AB-XXXXXXXX` code from their email |
| Name + phone | Last name (partial match) and phone number (partial match) |

### Confirmation number

Every booking is assigned a unique confirmation number (`AB-` + 8 random unambiguous characters, ~1 billion combinations) on creation. It appears:
- Prominently on the post-booking confirmation page
- In the subject line and body of all transactional emails (received, approved, cancelled)
- In the admin booking list and detail view (searchable)

---

## Customer Cancellation Requests

From the lookup results page, customers can request cancellation for any active booking via a **Request Cancellation** button. This starts an async workflow — the booking is not cancelled immediately.

### Customer flow

1. Customer finds their booking at `/bookings/find/`
2. Clicks **Request Cancellation**
3. Enters a reason (required) and submits
4. Receives an acknowledgement email; sees a success screen

Submitting a second request on the same booking shows an "already requested" screen — no duplicate requests possible.

### Admin flow

1. Admin receives an email alert with the customer's reason and a direct link to the booking in the admin panel
2. A **⚠ Requested** amber badge appears on the booking in the admin list
3. Admin filters by **Cancellation Requested = Yes** to see all pending requests
4. Processes it using the existing **❌ Cancel with refund & notify customer** action (selects refund type, enters reason, fires the cancellation email)

### Email notifications

| Trigger | Recipient | Template |
|---|---|---|
| Customer submits request | Customer | `cancellation_request_customer.html` |
| Customer submits request | Super-admin + area admins | `cancellation_request_admin.html` |

---

## Payment Gateway

Online payments are **feature-flagged per country**. When disabled for a country, bookings proceed as offline/cash — no payment gateway is invoked. When enabled, customers are redirected to the gateway checkout immediately after submitting a booking.

### Current gateways

| Gateway | Region | Status |
|---|---|---|
| Razorpay | India (UPI, Cards, Net Banking) | Live |
| Stripe | International | Stub (add credentials to activate) |
| Cashfree | India / SEA | Stub |
| Paystack | Africa | Stub |

### Enabling payments for a country

1. Go to **Admin → Payment Gateway Configs → Add**
2. Select the **Country** (e.g. India)
3. Choose the **Gateway** (e.g. Razorpay)
4. Tick **Is Enabled**
5. Save — bookings for that country now redirect to payment after submission

### Adding a new gateway

1. Create `payments/gateways/<slug>_gateway.py` implementing `BasePaymentGateway`
2. Add it to `GATEWAY_REGISTRY` in `payments/gateways/registry.py`
3. Add the slug + label to `PaymentGatewayConfig.GATEWAY_CHOICES` in `payments/models.py`
4. Create `templates/payments/checkout_<slug>.html`
5. Store API credentials in `.env` / Secret Manager

No changes to views or booking flow are needed — the registry resolves the right gateway automatically.

---

## CI/CD Pipeline

Every push to `main` triggers a 3-stage GitHub Actions workflow:

```
push to main
  │
  ├─ test    Django system checks + unit tests
  │          (runs against a real Postgres container, not mocks)
  │
  ├─ build   docker build → push to Artifact Registry (us-central1)
  │
  └─ deploy  gcloud run deploy
               ├─ Cloud SQL Auth Proxy (Unix socket, no sidecar needed)
               ├─ Secrets pulled from Google Secret Manager
               └─ python manage.py migrate runs on container startup
```

Authentication uses **Workload Identity Federation** — no service account JSON keys stored in GitHub.

### GitHub Secrets required

| Secret | Description |
|---|---|
| `GCP_PROJECT_ID` | Google Cloud project ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | WIF provider resource name |
| `GCP_SERVICE_ACCOUNT` | Deployer service account email |
| `CLOUD_SQL_INSTANCE` | e.g. `project:us-central1:any-booking-db` |
| `CLOUD_RUN_HOST` | Cloud Run URL (set after first deploy) |

App secrets (`DATABASE_URL`, `DJANGO_SECRET_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `ADMIN_NOTIFY_EMAIL`, `SITE_URL`) are stored in **Google Secret Manager** and injected by Cloud Run — they never touch GitHub. Gateway credentials (e.g. `RAZORPAY_KEY_ID`) are only required when that gateway is enabled in Admin → Payment Gateway Configs.

---

## Quick Start (Local)

```bash
# 1. Clone and install
git clone https://github.com/josetonyin/any-booking.git
cd any-booking
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY and DATABASE_URL

# 3. Migrate and create admin user
python manage.py migrate
python manage.py createsuperuser

# 4. Import sample hall data (optional — real data)
python manage.py import_halls path/to/halls.xlsx

# 5. Seed all categories + USA/Canada/UAE sample data (optional — demo data)
python manage.py seed_sample_data

# 6. Run
python manage.py runserver
```

| URL | Description |
|---|---|
| http://127.0.0.1:8000/ | Public site |
| http://127.0.0.1:8000/admin/ | Admin portal |
| http://127.0.0.1:8000/admin/dashboard/ | Admin dashboard |
| http://127.0.0.1:8000/vendor/login/ | Vendor portal login |

For full GCP deployment instructions see [SETUP.md](SETUP.md).

---

## Admin Credentials (local dev)

```
Username: admin
Password: admin1234
```

> Change before deploying to production.

---

## License

MIT
