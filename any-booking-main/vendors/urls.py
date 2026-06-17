from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.vendor_login_view, name='vendor_login'),
    path('logout/', views.vendor_logout_view, name='vendor_logout'),
    path('dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('bookings/', views.vendor_bookings, name='vendor_bookings'),
]
