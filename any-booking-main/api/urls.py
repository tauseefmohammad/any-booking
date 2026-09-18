# api/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# This file maps URL addresses to their handler functions (views).
# Example: GET /api/categories/ → CategoryListView
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path
from . import views

urlpatterns = [
    # ── Locations ─────────────────────────────────────────────────────────────
    path('countries/', views.CountryListView.as_view(), name='api-countries'),
    path('states/', views.StateListView.as_view(), name='api-states'),
    path('districts/', views.DistrictListView.as_view(), name='api-districts'),
    path('cities/', views.CityListView.as_view(), name='api-cities'),
    path('cities/nearest/', views.NearestCityView.as_view(), name='api-nearest-city'),

    # ── Categories ────────────────────────────────────────────────────────────
    path('categories/', views.CategoryListView.as_view(), name='api-categories'),

    # ── Services ──────────────────────────────────────────────────────────────
    path('services/', views.ServiceListView.as_view(), name='api-services'),
    path('services/<slug:slug>/', views.ServiceDetailView.as_view(), name='api-service-detail'),

    # ── Availability ──────────────────────────────────────────────────────────
    path('services/<slug:slug>/blocked-dates/', views.BlockedDatesView.as_view(), name='api-blocked-dates'),

    # ── Reviews ───────────────────────────────────────────────────────────────
    path('services/<slug:slug>/reviews/', views.ReviewListView.as_view(), name='api-reviews'),
    path('services/<slug:slug>/reviews/add/', views.ReviewCreateView.as_view(), name='api-review-add'),

    # ── Bookings ──────────────────────────────────────────────────────────────
    path('bookings/create/', views.BookingCreateView.as_view(), name='api-booking-create'),
    path('bookings/lookup/', views.BookingLookupView.as_view(), name='api-booking-lookup'),
    path('bookings/<str:confirmation_number>/', views.BookingDetailView.as_view(), name='api-booking-detail'),
    path('bookings/<str:confirmation_number>/cancel-request/', views.CancellationRequestView.as_view(), name='api-cancel-request'),

    # ── Payments ──────────────────────────────────────────────────────────────
    path('payments/initiate/', views.PaymentInitiateView.as_view(), name='api-payment-initiate'),
    path('payments/callback/', views.PaymentCallbackView.as_view(), name='api-payment-callback'),
]