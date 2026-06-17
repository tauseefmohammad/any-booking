from django.test import TestCase, Client
from django.urls import reverse
from services.models import (
    Category, City, District, State, Country,
)


def _make_location():
    country = Country.objects.create(
        name='India', code='IN', currency='INR',
        currency_symbol='₹', phone_code='+91',
    )
    state = State.objects.create(country=country, name='Maharashtra')
    district = District.objects.create(state=state, name='Pune District')
    return district


class CategoryImageFieldTest(TestCase):
    def test_image_field_exists_and_is_blank_by_default(self):
        cat = Category(slug='banquet_hall', icon='bi-building')
        cat.save()
        self.assertTrue(hasattr(cat, 'image'))
        self.assertFalse(bool(cat.image))  # blank by default


class CityFeaturedFieldsTest(TestCase):
    def setUp(self):
        self.district = _make_location()

    def test_is_featured_defaults_to_false(self):
        city = City.objects.create(district=self.district, name='Pune')
        self.assertFalse(city.is_featured)

    def test_image_field_exists_and_is_blank_by_default(self):
        city = City.objects.create(district=self.district, name='Pune')
        self.assertFalse(bool(city.image))

    def test_featured_city_appears_in_filtered_queryset(self):
        City.objects.create(district=self.district, name='NotFeatured')
        featured = City.objects.create(
            district=self.district, name='Featured', is_featured=True,
        )
        qs = City.objects.filter(is_featured=True)
        self.assertIn(featured, qs)
        self.assertEqual(qs.count(), 1)


class HomeViewContextTest(TestCase):
    def setUp(self):
        self.district = _make_location()

    def test_featured_cities_in_context(self):
        city = City.objects.create(
            district=self.district, name='Mumbai', is_featured=True,
        )
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('featured_cities', response.context)
        self.assertIn(city, response.context['featured_cities'])

    def test_non_featured_city_not_in_context(self):
        City.objects.create(district=self.district, name='Hidden')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['featured_cities'].count(), 0)
