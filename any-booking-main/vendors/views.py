from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from bookings.models import Booking
from services.models import Vendor


def vendor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('vendor_login')
        vendor = getattr(request.user, 'vendor_profile', None)
        if vendor is None:
            logout(request)
            messages.error(request, 'This account is not linked to a vendor.')
            return redirect('vendor_login')
        return view_func(request, *args, vendor=vendor, **kwargs)
    return wrapper


def vendor_login_view(request):
    if request.user.is_authenticated and hasattr(request.user, 'vendor_profile'):
        return redirect('vendor_dashboard')

    form = AuthenticationForm(data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if hasattr(user, 'vendor_profile'):
            login(request, user)
            return redirect('vendor_dashboard')
        messages.error(request, 'This account is not linked to a vendor.')

    return render(request, 'vendors/login.html', {'form': form})


def vendor_logout_view(request):
    logout(request)
    return redirect('vendor_login')


@vendor_required
def vendor_dashboard(request, vendor=None):
    services = vendor.services.filter(is_active=True).order_by('name')
    service_ids = list(services.values_list('id', flat=True))

    recent_bookings = (
        Booking.objects
        .filter(service__in=service_ids)
        .select_related('service')
        .order_by('-created_at')[:10]
    )
    pending_count = Booking.objects.filter(service__in=service_ids, status=Booking.STATUS_PENDING).count()
    confirmed_count = Booking.objects.filter(service__in=service_ids, status=Booking.STATUS_CONFIRMED).count()

    return render(request, 'vendors/dashboard.html', {
        'vendor': vendor,
        'services': services,
        'recent_bookings': recent_bookings,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
    })


@vendor_required
def vendor_bookings(request, vendor=None):
    service_ids = list(vendor.services.values_list('id', flat=True))
    bookings_qs = (
        Booking.objects
        .filter(service__in=service_ids)
        .select_related('service')
        .order_by('-created_at')
    )

    selected_status = request.GET.get('status', '')
    selected_service = request.GET.get('service', '')

    if selected_status:
        bookings_qs = bookings_qs.filter(status=selected_status)
    if selected_service:
        bookings_qs = bookings_qs.filter(service_id=selected_service)

    return render(request, 'vendors/bookings.html', {
        'vendor': vendor,
        'bookings': bookings_qs,
        'services': vendor.services.order_by('name'),
        'status_choices': Booking.STATUS_CHOICES,
        'selected_status': selected_status,
        'selected_service': selected_service,
    })
