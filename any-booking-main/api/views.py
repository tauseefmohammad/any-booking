# api/views.py
# ─────────────────────────────────────────────────────────────────────────────
# Views handle incoming API requests from Flutter and return JSON responses.
# Each View class handles one URL endpoint.
# ─────────────────────────────────────────────────────────────────────────────
import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q

from services.models import (
    Country, State, District, City,
    Category, Service,
)
from bookings.models import Booking, BlockedDate
from reviews.models import Review
from payments.models import PaymentGatewayConfig
from payments.gateways.registry import get_gateway_for_country

from .serializers import (
    CountrySerializer, StateSerializer,
    DistrictSerializer, CitySerializer,
    CategorySerializer,
    ServiceListSerializer, ServiceDetailSerializer,
    ReviewSerializer, ReviewCreateSerializer,
    BookingCreateSerializer, BookingDetailSerializer,
    BlockedDateSerializer,
)


# ── Location Views ────────────────────────────────────────────────────────────

class CountryListView(APIView):
    # GET /api/countries/
    # Returns list of all countries
    def get(self, request):
        countries = Country.objects.all().order_by('name')
        serializer = CountrySerializer(countries, many=True)
        # many=True means we're serializing a list not a single object
        return Response(serializer.data)


class StateListView(APIView):
    # GET /api/states/?country=1
    # Returns states, optionally filtered by country id
    def get(self, request):
        country_id = request.query_params.get('country')
        # query_params reads URL parameters like ?country=1
        if country_id:
            states = State.objects.filter(country_id=country_id).order_by('name')
        else:
            states = State.objects.all().order_by('name')
        serializer = StateSerializer(states, many=True)
        return Response(serializer.data)


class DistrictListView(APIView):
    # GET /api/districts/?state=1
    # Returns districts, optionally filtered by state id
    def get(self, request):
        state_id = request.query_params.get('state')
        if state_id:
            districts = District.objects.filter(state_id=state_id).order_by('name')
        else:
            districts = District.objects.all().order_by('name')
        serializer = DistrictSerializer(districts, many=True)
        return Response(serializer.data)


class CityListView(APIView):
    # GET /api/cities/?district=1
    # Returns cities, optionally filtered by district id
    def get(self, request):
        district_id = request.query_params.get('district')
        if district_id:
            cities = City.objects.filter(district_id=district_id).order_by('name')
        else:
            cities = City.objects.all().order_by('name')
        serializer = CitySerializer(cities, many=True)
        return Response(serializer.data)


# ── Category Views ────────────────────────────────────────────────────────────

class CategoryListView(APIView):
    # GET /api/categories/
    # Returns all active categories
    def get(self, request):
        categories = Category.objects.all().order_by('slug')
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


# ── Service Views ─────────────────────────────────────────────────────────────

class ServiceListView(APIView):
    # GET /api/services/
    # Supports filters: ?category=banquet-halls&city=1&search=grand
    def get(self, request):
        services = Service.objects.filter(is_active=True)

        # Filter by category slug if provided
        category_slug = request.query_params.get('category')
        if category_slug:
            services = services.filter(category__slug=category_slug)

        # Filter by city id if provided
        city_id = request.query_params.get('city')
        if city_id:
            services = services.filter(city_id=city_id)

        # Filter by state id if provided
        state_id = request.query_params.get('state')
        if state_id:
            services = services.filter(city__district__state_id=state_id)

        # Search by name if provided
        search = request.query_params.get('search')
        if search:
            services = services.filter(name__icontains=search)
            # icontains = case-insensitive search

        services = services.order_by('name')
        serializer = ServiceListSerializer(
            services,
            many=True,
            context={'request': request}
            # context passes the request so we can build absolute image URLs
        )
        return Response(serializer.data)


class ServiceDetailView(APIView):
    # GET /api/services/grand-palace-banquet/
    # Returns full detail of a single service
    def get(self, request, slug):
        # get_object_or_404 returns 404 error if service not found
        service = get_object_or_404(Service, slug=slug, is_active=True)
        serializer = ServiceDetailSerializer(
            service,
            context={'request': request}
        )
        return Response(serializer.data)


# ── Availability Views ────────────────────────────────────────────────────────

class BlockedDatesView(APIView):
    # GET /api/services/grand-palace-banquet/blocked-dates/
    # Returns all dates that cannot be booked
    def get(self, request, slug):
        service = get_object_or_404(Service, slug=slug)

        # Get admin blocked dates for this service
        blocked = BlockedDate.objects.filter(service=service)

        # Get dates that already have confirmed/pending bookings
        booked_dates = Booking.objects.filter(
            service=service,
            status__in=['pending', 'confirmed']
        ).values_list('event_date', flat=True)
        # values_list returns just the dates, not full objects
        # flat=True returns a simple list instead of list of tuples

        # Combine both into one list
        blocked_dates = list(blocked.values_list('date', flat=True))
        all_blocked = list(set(list(booked_dates) + blocked_dates))
        # set() removes duplicates

        return Response({'blocked_dates': all_blocked})


# ── Review Views ──────────────────────────────────────────────────────────────

class ReviewListView(APIView):
    # GET /api/services/grand-palace-banquet/reviews/
    # Returns all approved reviews for a service
    def get(self, request, slug):
        service = get_object_or_404(Service, slug=slug)
        reviews = Review.objects.filter(
            service=service,
            status='approved'
        ).order_by('-created_at')
        # -created_at means newest first (minus = descending)
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)


class ReviewCreateView(APIView):
    # POST /api/services/grand-palace-banquet/reviews/add/
    # Flutter submits a new review
    def post(self, request, slug):
        service = get_object_or_404(Service, slug=slug)
        serializer = ReviewCreateSerializer(data=request.data)
        # request.data contains the JSON body Flutter sent

        if serializer.is_valid():
            # Save review with status=pending (goes to moderation)
            serializer.save(service=service, status='pending')
            return Response(
                {'message': 'Review submitted. It will appear after moderation.'},
                status=status.HTTP_201_CREATED
                # 201 = Created (success)
            )
        # If validation fails, return errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # 400 = Bad Request


# ── Booking Views ─────────────────────────────────────────────────────────────

class BookingCreateView(APIView):
    # POST /api/bookings/create/
    # Flutter submits a new booking
    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)

        if serializer.is_valid():
            # Get the service to calculate total_amount from its base_price
            service = serializer.validated_data.get('service')
            total_amount = service.base_price if service else 0

            booking = serializer.save(
                status='pending',
                total_amount=total_amount,   # ← NEW: required field, no default
                advance_amount=0,            # explicit, matches model default
            )
            # Return the booking detail including confirmation number
            detail = BookingDetailSerializer(booking)
            return Response(detail.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 


class BookingLookupView(APIView):
    # GET /api/bookings/lookup/?confirmation=AB-12345678
    # GET /api/bookings/lookup/?last_name=Smith&phone=9999999999
    # Customer finds their booking without an account
    def get(self, request):
        confirmation = request.query_params.get('confirmation')
        last_name = request.query_params.get('last_name')
        phone = request.query_params.get('phone')

        # Only show active bookings
        bookings = Booking.objects.filter(status__in=['pending', 'confirmed'])

        if confirmation:
            # Search by confirmation number
            bookings = bookings.filter(
                confirmation_number__iexact=confirmation
                # iexact = case-insensitive exact match
            )
        elif last_name and phone:
            # Search by last name + phone
            bookings = bookings.filter(
                customer_name__icontains=last_name,
                customer_phone__icontains=phone,
            )
        else:
            return Response(
                {'error': 'Provide confirmation number or last name + phone'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BookingDetailSerializer(bookings, many=True)
        return Response(serializer.data)


class BookingDetailView(APIView):
    # GET /api/bookings/AB-12345678/
    # Returns detail of a single booking
    def get(self, request, confirmation_number):
        booking = get_object_or_404(
            Booking,
            confirmation_number__iexact=confirmation_number
        )
        serializer = BookingDetailSerializer(booking)
        return Response(serializer.data)


class CancellationRequestView(APIView):
    # POST /api/bookings/AB-12345678/cancel-request/
    # Customer requests cancellation
    def post(self, request, confirmation_number):
        booking = get_object_or_404(
            Booking,
            confirmation_number__iexact=confirmation_number,
            status__in=['pending', 'confirmed']
        )

        # Check if already requested
        if booking.cancellation_requested:
            return Response(
                {'error': 'Cancellation already requested for this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'error': 'Please provide a reason for cancellation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark cancellation requested
        booking.cancellation_requested = True
        booking.cancellation_reason = reason
        booking.save()

        return Response(
            {'message': 'Cancellation request submitted. Admin will process it shortly.'},
            status=status.HTTP_200_OK
        )


# ── Payment Views ─────────────────────────────────────────────────────────────

class PaymentInitiateView(APIView):
    # POST /api/payments/initiate/
    # Flutter calls this to start payment for a booking
    def post(self, request):
        booking_id = request.data.get('booking_id')
        if not booking_id:
            return Response(
                {'error': 'booking_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking = get_object_or_404(Booking, id=booking_id)

        # Check if payment gateway is enabled for this country
        try:
            country = booking.service.city.district.state.country
            gateway_config = PaymentGatewayConfig.objects.get(
                country=country,
                is_enabled=True
            )
            gateway = get_gateway_for_country(country)
            order_data = gateway.initiate_payment(booking)
            return Response(order_data, status=status.HTTP_200_OK)

        except PaymentGatewayConfig.DoesNotExist:
            # No payment gateway configured - offline/cash booking
            return Response(
                {'payment_required': False,
                 'message': 'This booking will be confirmed offline'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentCallbackView(APIView):
    # POST /api/payments/callback/
    # Called after payment is completed on Flutter side
    def post(self, request):
        try:
            country_id = request.data.get('country_id')
            country = get_object_or_404(Country, id=country_id)
            gateway = get_gateway_for_country(country)
            result = gateway.verify_payment(request.data)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
# ── Nearest City View ─────────────────────────────────────────────────────────

class NearestCityView(APIView):
    # GET /api/cities/nearest/?lat=17.3850&lng=78.4867
    # Returns the nearest city to given GPS coordinates
    def get(self, request):
        try:
            lat = float(request.query_params.get('lat', 0))
            lng = float(request.query_params.get('lng', 0))
        except ValueError:
            return Response(
                {'error': 'Invalid coordinates'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get all cities that have coordinates set
        cities = City.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            is_active=True
        )

        if not cities.exists():
            return Response(
                {'error': 'No cities with coordinates found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Find nearest city using Haversine distance formula
        def haversine(lat1, lng1, lat2, lng2):
            # calculates distance in km between two GPS coordinates
            R = 6371  # Earth radius in km
            dlat = math.radians(float(lat2) - lat1)
            dlng = math.radians(float(lng2) - lng1)
            a = (math.sin(dlat/2)**2 +
                 math.cos(math.radians(lat1)) *
                 math.cos(math.radians(float(lat2))) *
                 math.sin(dlng/2)**2)
            return R * 2 * math.asin(math.sqrt(a))

        nearest = min(
            cities,
            key=lambda c: haversine(lat, lng, c.latitude, c.longitude)
        )

        serializer = CitySerializer(nearest)
        return Response(serializer.data)