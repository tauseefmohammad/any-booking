# api/serializers.py
# ─────────────────────────────────────────────────────────────────────────────
# Serializers convert Django model objects into JSON that Flutter can read.
# Think of them as a "translator" between Python objects and JSON.
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework import serializers
from services.models import (
    Country, State, District, City,
    Category, Service, ServiceImage,       # ← ServiceImage (not ServicePhoto)
    ServiceAttributeValue, AttributeDefinition,
)
from bookings.models import Booking, BlockedDate
from reviews.models import Review


# ── Location Serializers ──────────────────────────────────────────────────────

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'currency', 'currency_symbol', 'phone_code']


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ['id', 'name', 'country']


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ['id', 'name', 'state']


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'district', 'latitude', 'longitude']


# ── Category Serializer ───────────────────────────────────────────────────────

class CategorySerializer(serializers.ModelSerializer):
    # 'name' doesn't exist as a field — Category uses slug + get_slug_display()
    # so we use a SerializerMethodField to compute the display name
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        # obj is a Category instance
        # display_name is a property defined in the model
        return obj.display_name

    class Meta:
        model = Category
        fields = ['id', 'slug', 'name', 'icon', 'image']


# ── Service Serializers ───────────────────────────────────────────────────────

class ServiceImageSerializer(serializers.ModelSerializer):
    # Serializes a single service image
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        # Build absolute URL so Flutter can download the image
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    class Meta:
        model = ServiceImage
        fields = ['id', 'image_url', 'caption', 'is_primary', 'order']


class AttributeValueSerializer(serializers.ModelSerializer):
    # Serializes a single attribute value (e.g. AC: Yes, Capacity: 500)
    attribute_name = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    def get_attribute_name(self, obj):
        # obj is a ServiceAttributeValue instance
        return obj.attribute.name

    def get_value(self, obj):
        # display_value is a property on ServiceAttributeValue model
        return obj.display_value

    class Meta:
        model = ServiceAttributeValue
        fields = ['attribute_name', 'value']


class ServiceListSerializer(serializers.ModelSerializer):
    # Used for listing services — less detail, faster loading
    category_name = serializers.SerializerMethodField()
    city_name = serializers.CharField(source='city.name', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    primary_photo = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        source='base_price',
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    def get_category_name(self, obj):
        return obj.category.display_name

    def get_average_rating(self, obj):
        reviews = obj.reviews.filter(status='approved')
        if not reviews.exists():
            return None
        total = sum(r.rating for r in reviews)
        return round(total / reviews.count(), 1)

    def get_review_count(self, obj):
        return obj.reviews.filter(status='approved').count()

    def get_primary_photo(self, obj):
        # Get the primary image or first image
        # 'images' is the related_name on ServiceImage
        photo = obj.images.filter(is_primary=True).first() or obj.images.first()
        if photo and photo.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(photo.image.url)
        return None

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'slug', 'category_name', 'city_name',
            'price', 'price_unit', 'is_active',
            'average_rating', 'review_count', 'primary_photo',
        ]


class ServiceDetailSerializer(serializers.ModelSerializer):
    # Used for single service detail page — full information
    category_name = serializers.SerializerMethodField()
    city_name = serializers.CharField(source='city.name', read_only=True)
    state_name = serializers.CharField(
        source='city.district.state.name',
        read_only=True
    )
    country_name = serializers.CharField(
        source='city.district.state.country.name',
        read_only=True
    )
    currency_symbol = serializers.CharField(read_only=True)
    # 'images' is the related_name on ServiceImage model
    photos = ServiceImageSerializer(
        source='images',
        many=True,
        read_only=True
    )
    # 'attribute_values' is the related_name on ServiceAttributeValue model
    attributes = AttributeValueSerializer(
        source='attribute_values',
        many=True,
        read_only=True
    )
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        source='base_price',
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    def get_category_name(self, obj):
        return obj.category.display_name

    def get_average_rating(self, obj):
        reviews = obj.reviews.filter(status='approved')
        if not reviews.exists():
            return None
        total = sum(r.rating for r in reviews)
        return round(total / reviews.count(), 1)

    def get_review_count(self, obj):
        return obj.reviews.filter(status='approved').count()

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'slug', 'description',
            'category_name', 'city_name', 'state_name', 'country_name',
            'price', 'price_unit', 'currency_symbol', 'is_active',
            'average_rating', 'review_count',
            'photos', 'attributes',
        ]


# ── Review Serializers ────────────────────────────────────────────────────────

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'reviewer_name', 'rating', 'body', 'created_at']


class ReviewCreateSerializer(serializers.ModelSerializer):
    # Used when Flutter submits a new review
    class Meta:
        model = Review
        fields = ['reviewer_name', 'rating', 'body']


# ── Booking Serializers ───────────────────────────────────────────────────────

class BookingCreateSerializer(serializers.ModelSerializer):
    # Used when Flutter submits a new booking
    class Meta:
        model = Booking
        fields = [
            'service', 'event_date', 'guest_count',
            'customer_name', 'customer_email', 'customer_phone',
            'special_requests',
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    # Used when customer looks up their booking
    service_name = serializers.CharField(source='service.name', read_only=True)
    city_name = serializers.CharField(source='service.city.name', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'confirmation_number', 'service_name', 'city_name',
            'event_date', 'guest_count', 'customer_name',
            'customer_email', 'customer_phone', 'special_requests',
            'status', 'total_amount', 'advance_amount',
            'created_at',
        ]


# ── Blocked Dates Serializer ──────────────────────────────────────────────────

class BlockedDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedDate
        fields = ['date']