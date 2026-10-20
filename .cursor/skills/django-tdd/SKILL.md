---

 name: django-tdd description: Django testing strategies with pytest-django, TDD methodology, factory_boy, mocking, coverage, and testing Django REST Framework APIs. Use when writing Django or DRF tests with pytest-django, or driving a Django feature test-first. metadata:   origin: ECC

 --- 

## Project adaptation (easy-exchange)

This project uses Django's built-in test runner

`python manage.py test`, `django.test.TestCase`), as required by

the specs in /specs. Do NOT switch to pytest or add pytest-django.

Use the patterns of this skill (test data helpers, isolation,

naming, one behavior per test) but with Django's TestCase.

Use plain helper functions instead of factory_boy unless it is

already installed.

 # Django Testing with TDD  Test-driven development for Django applications using pytest, factory_boy, and Django REST Framework.  ## When to Activate  - Writing new Django applications - Implementing Django REST Framework APIs - Testing Django models, views, and serializers - Setting up testing infrastructure for Django projects  ## TDD Workflow for Django  ### Red-Green-Refactor Cycle  ```python # Step 1: RED - Write failing test def test_user_creation():     user = User.objects.create_user([email='test@example.com](mailto:email='test@example.com)', password='testpass123')
    assert [user.email](http://user.email) == '[test@example.com](mailto:test@example.com)'
    assert user.check_password('testpass123')
    assert not [user.is](http://user.is)_staff

# Step 2: GREEN - Make test pass
# Create User model or factory

# Step 3: REFACTOR - Improve while keeping tests green
```

## Setup

### pytest Configuration

```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.test
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --reuse-db
    --nomigrations
    --cov=apps
    --cov-report=html
    --cov-report=term-missing
    --strict-markers
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
```

### Test Settings

```python
# config/settings/[test.py](http://test.py)
from .base import 

*DEBUG = True
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable migrations for speed
class DisableMigrations:
    def **contains**(self, item):
        return True

    def **getitem**(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Faster password hashing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Celery always eager
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

### [conftest.py](http://conftest.py)

```python
# tests/[conftest.py](http://conftest.py)
import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture(autouse=True)
def timezone_settings(settings):
    """Ensure consistent timezone."""
    settings.TIME_ZONE = 'UTC'

@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        [email='test@example.com](mailto:email='test@example.com)',
        password='testpass123',
        username='testuser'
    )

@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        [email='admin@example.com](mailto:email='admin@example.com)',
        password='adminpass123',
        username='admin'
    )

@pytest.fixture
def authenticated_client(client, user):
    """Return authenticated client."""
    client.force_login(user)
    return client

@pytest.fixture
def api_client():
    """Return DRF API client."""
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def authenticated_api_client(api_client, user):
    """Return authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client
```

## Factory Boy

### Factory Setup

```python
# tests/[factories.py](http://factories.py)
import factory
from factory import fuzzy
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from apps.products.models import Product, Category

User = get_user_model()

class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model."""

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"[user{n}@example.com](mailto:user{n}@example.com)")
    username = factory.Sequence(lambda n: f"user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True

class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory for Category model."""

    class Meta:
        model = Category

    name = factory.Faker('word')
    slug = factory.LazyAttribute(lambda obj: [obj.name](http://obj.name).lower())
    description = factory.Faker('text')

class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for Product model."""

    class Meta:
        model = Product

    name = factory.Faker('sentence', nb_words=3)
    slug = factory.LazyAttribute(lambda obj: [obj.name](http://obj.name).lower().replace(' ', '-'))
    description = factory.Faker('text')
    price = fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    stock = fuzzy.FuzzyInteger(0, 100)
    is_active = True
    category = factory.SubFactory(CategoryFactory)
    created_by = factory.SubFactory(UserFactory)

    @[factory.post](http://factory.post)_generation
    def tags(self, create, extracted,* *kwargs):
        """Add tags to product."""
        if not create:
            return
        if extracted:
            for tag in extracted:
                self.tags.add(tag)
```

### Using Factories

```python
# tests/test_[models.py](http://models.py)
import pytest
from tests.factories import ProductFactory, UserFactory

def test_product_creation():
    """Test product creation using factory."""
    product = ProductFactory(price=100.00, stock=50)
    assert product.price == 100.00
    assert product.stock == 50
    assert [product.is](http://product.is)_active is True

def test_product_with_tags():
    """Test product with tags."""
    tags = [TagFactory(name='electronics'), TagFactory(name='new')]
    product = ProductFactory(tags=tags)
    assert product.tags.count() == 2

def test_multiple_products():
    """Test creating multiple products."""
    products = ProductFactory.create_batch(10)
    assert len(products) == 10
```

## Model Testing

### Model Tests

```python
# tests/test_[models.py](http://models.py)
import pytest
from django.core.exceptions import ValidationError
from tests.factories import UserFactory, ProductFactory

class TestUserModel:
    """Test User model."""

    def test_create_user(self, db):
        """Test creating a regular user."""
        user = UserFactory([email='test@example.com](mailto:email='test@example.com)')
        assert [user.email](http://user.email) == '[test@example.com](mailto:test@example.com)'
        assert user.check_password('testpass123')
        assert not [user.is](http://user.is)_staff
        assert not [user.is](http://user.is)_superuser

    def test_create_superuser(self, db):
        """Test creating a superuser."""
        user = UserFactory(
            [email='admin@example.com](mailto:email='admin@example.com)',
            is_staff=True,
            is_superuser=True
        )
        assert [user.is](http://user.is)_staff
        assert [user.is](http://user.is)_superuser

    def test_user_str(self, db):
        """Test user string representation."""
        user = UserFactory([email='test@example.com](mailto:email='test@example.com)')
        assert str(user) == '[test@example.com](mailto:test@example.com)'

class TestProductModel:
    """Test Product model."""

    def test_product_creation(self, db):
        """Test creating a product."""
        product = ProductFactory()
        assert [product.id](http://product.id) is not None
        assert [product.is](http://product.is)_active is True
        assert product.created_at is not None

    def test_product_slug_generation(self, db):
        """Test automatic slug generation."""
        product = ProductFactory(name='Test Product')
        assert product.slug == 'test-product'

    def test_product_price_validation(self, db):
        """Test price cannot be negative."""
        product = ProductFactory(price=-10)
        with pytest.raises(ValidationError):
            product.full_clean()

    def test_product_manager_active(self, db):
        """Test active manager method."""
        ProductFactory.create_batch(5, is_active=True)
        ProductFactory.create_batch(3, is_active=False)

        active_count = Product.objects.active().count()
        assert active_count == 5

    def test_product_stock_management(self, db):
        """Test stock management."""
        product = ProductFactory(stock=10)
        product.reduce_stock(5)
        product.refresh_from_db()
        assert product.stock == 5

        with pytest.raises(ValueError):
            product.reduce_stock(10)  # Not enough stock
```

## View Testing

### Django View Testing

```python
# tests/test_[views.py](http://views.py)
import pytest
from django.urls import reverse
from tests.factories import ProductFactory, UserFactory

class TestProductViews:
    """Test product views."""

    def test_product_list(self, client, db):
        """Test product list view."""
        ProductFactory.create_batch(10)

        response = client.get(reverse('products:list'))

        assert response.status_code == 200
        assert len(response.context['products']) == 10

    def test_product_detail(self, client, db):
        """Test product detail view."""
        product = ProductFactory()

        response = client.get(reverse('products:detail', kwargs={'slug': product.slug}))

        assert response.status_code == 200
        assert response.context['product'] == product

    def test_product_create_requires_login(self, client, db):
        """Test product creation requires authentication."""
        response = client.get(reverse('products:create'))

        assert response.status_code == 302
        assert response.url.startswith('/accounts/login/')

    def test_product_create_authenticated(self, authenticated_client, db):
        """Test product creation as authenticated user."""
        response = authenticated_client.get(reverse('products:create'))

        assert response.status_code == 200

    def test_product_create_post(self, authenticated_client, db, category):
        """Test creating a product via POST."""
        data = {
            'name': 'Test Product',
            'description': 'A test product',
            'price': '99.99',
            'stock': 10,
            'category': [category.id](http://category.id),
        }

        response = authenticated_[client.post](http://client.post)(reverse('products:create'), data)

        assert response.status_code == 302
        assert Product.objects.filter(name='Test Product').exists()
```

## DRF API Testing

### Serializer Testing

```python
# tests/test_[serializers.py](http://serializers.py)
import pytest
from rest_framework.exceptions import ValidationError
from apps.products.serializers import ProductSerializer
from tests.factories import ProductFactory

class TestProductSerializer:
    """Test ProductSerializer."""

    def test_serialize_product(self, db):
        """Test serializing a product."""
        product = ProductFactory()
        serializer = ProductSerializer(product)

        data = [serializer.data](http://serializer.data)

        assert data['id'] == [product.id](http://product.id)
        assert data['name'] == [product.name](http://product.name)
        assert data['price'] == str(product.price)

    def test_deserialize_product(self, db):
        """Test deserializing product data."""
        data = {
            'name': 'Test Product',
            'description': 'Test description',
            'price': '99.99',
            'stock': 10,
            'category': 1,
        }

        serializer = ProductSerializer(data=data)

        assert [serializer.is](http://serializer.is)_valid()
        product = [serializer.save](http://serializer.save)()

        assert [product.name](http://product.name) == 'Test Product'
        assert float(product.price) == 99.99

    def test_price_validation(self, db):
        """Test price validation."""
        data = {
            'name': 'Test Product',
            'price': '-10.00',
            'stock': 10,
        }

        serializer = ProductSerializer(data=data)

        assert not [serializer.is](http://serializer.is)_valid()
        assert 'price' in serializer.errors

    def test_stock_validation(self, db):
        """Test stock cannot be negative."""
        data = {
            'name': 'Test Product',
            'price': '99.99',
            'stock': -5,
        }

        serializer = ProductSerializer(data=data)

        assert not [serializer.is](http://serializer.is)_valid()
        assert 'stock' in serializer.errors
```

### API ViewSet Testing

```python
# tests/test_[api.py](http://api.py)
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from tests.factories import ProductFactory, UserFactory

class TestProductAPI:
    """Test Product API endpoints."""

    @pytest.fixture
    def api_client(self):
        """Return API client."""
        return APIClient()

    def test_list_products(self, api_client, db):
        """Test listing products."""
        ProductFactory.create_batch(10)

        url = reverse('api:product-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert [response.data](http://response.data)['count'] == 10

    def test_retrieve_product(self, api_client, db):
        """Test retrieving a product."""
        product = ProductFactory()

        url = reverse('api:product-detail', kwargs={'pk': [product.id](http://product.id)})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert [response.data](http://response.data)['id'] == [product.id](http://product.id)

    def test_create_product_unauthorized(self, api_client, db):
        """Test creating product without authentication."""
        url = reverse('api:product-list')
        data = {'name': 'Test Product', 'price': '99.99'}

        response = api_[client.post](http://client.post)(url, data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_product_authorized(self, authenticated_api_client, db):
        """Test creating product as authenticated user."""
        url = reverse('api:product-list')
        data = {
            'name': 'Test Product',
            'description': 'Test',
            'price': '99.99',
            'stock': 10,
        }

        response = authenticated_api_[client.post](http://client.post)(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert [response.data](http://response.data)['name'] == 'Test Product'

    def test_update_product(self, authenticated_api_client, db):
        """Test updating a product."""
        product = ProductFactory(created_by=authenticated_api_client.user)

        url = reverse('api:product-detail', kwargs={'pk': [product.id](http://product.id)})
        data = {'name': 'Updated Product'}

        response = authenticated_api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert [response.data](http://response.data)['name'] == 'Updated Product'

    def test_delete_product(self, authenticated_api_client, db):
        """Test deleting a product."""
        product = ProductFactory(created_by=authenticated_api_client.user)

        url = reverse('api:product-detail', kwargs={'pk': [product.id](http://product.id)})
        response = authenticated_api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_filter_products_by_price(self, api_client, db):
        """Test filtering products by price."""
        ProductFactory(price=50)
        ProductFactory(price=150)

        url = reverse('api:product-list')
        response = api_client.get(url, {'price_min': 100})

        assert response.status_code == status.HTTP_200_OK
        assert [response.data](http://response.data)['count'] == 1

    def test_search_products(self, api_client, db):
        """Test searching products."""
        ProductFactory(name='Apple iPhone')
        ProductFactory(name='Samsung Galaxy')

        url = reverse('api:product-list')
        response = api_client.get(url, {'search': 'Apple'})

        assert response.status_code == status.HTTP_200_OK
        assert [response.data](http://response.data)['count'] == 1
```

## Mocking and Patching

### Mocking External Services

```python
# tests/test_[views.py](http://views.py)
from unittest.mock import patch, Mock
import pytest

class TestPaymentView:
    """Test payment view with mocked payment gateway."""

    @patch('[apps.payments.services](http://apps.payments.services).stripe')
    def test_successful_payment(self, mock_stripe, client, user, product):
        """Test successful payment with mocked Stripe."""
        # Configure mock
        mock_stripe.Charge.create.return_value = {
            'id': 'ch_123',
            'status': 'succeeded',
            'amount': 9999,
        }

        client.force_login(user)
        response = [client.post](http://client.post)(reverse('payments:process'), {
            'product_id': [product.id](http://product.id),
            'token': 'tok_visa',
        })

        assert response.status_code == 302
        mock_stripe.Charge.create.assert_called_once()

    @patch('[apps.payments.services](http://apps.payments.services).stripe')
    def test_failed_payment(self, mock_stripe, client, user, product):
        """Test failed payment."""
        mock_stripe.Charge.create.side_effect = Exception('Card declined')

        client.force_login(user)
        response = [client.post](http://client.post)(reverse('payments:process'), {
            'product_id': [product.id](http://product.id),
            'token': 'tok_visa',
        })

        assert response.status_code == 302
        assert 'error' in response.url
```

### Mocking Email Sending

```python
# tests/test_[email.py](http://email.py)
from django.core import mail
from django.test import override_settings

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def test_order_confirmation_email(db, order):
    """Test order confirmation email."""
    order.send_confirmation_email()

    assert len(mail.outbox) == 1
    assert [order.user.email](http://order.user.email) in mail.outbox[0].to
    assert 'Order Confirmation' in mail.outbox[0].subject
```

## Integration Testing

### Full Flow Testing

```python
# tests/test_[integration.py](http://integration.py)
import pytest
from django.urls import reverse
from tests.factories import UserFactory, ProductFactory

class TestCheckoutFlow:
    """Test complete checkout flow."""

    def test_guest_to_purchase_flow(self, client, db):
        """Test complete flow from guest to purchase."""
        # Step 1: Register
        response = [client.post](http://client.post)(reverse('users:register'), {
            'email': '[test@example.com](mailto:test@example.com)',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
        })
        assert response.status_code == 302

        # Step 2: Login
        response = [client.post](http://client.post)(reverse('users:login'), {
            'email': '[test@example.com](mailto:test@example.com)',
            'password': 'testpass123',
        })
        assert response.status_code == 302

        # Step 3: Browse products
        product = ProductFactory(price=100)
        response = client.get(reverse('products:detail', kwargs={'slug': product.slug}))
        assert response.status_code == 200

        # Step 4: Add to cart
        response = [client.post](http://client.post)(reverse('cart:add'), {
            'product_id': [product.id](http://product.id),
            'quantity': 1,
        })
        assert response.status_code == 302

        # Step 5: Checkout
        response = client.get(reverse('checkout:review'))
        assert response.status_code == 200
        assert [product.name](http://product.name) in response.content.decode()

        # Step 6: Complete purchase
        with patch('[apps.checkout.services](http://apps.checkout.services).process_payment') as mock_payment:
            mock_payment.return_value = True
            response = [client.post](http://client.post)(reverse('checkout:complete'))

        assert response.status_code == 302
        assert Order.objects.filter([user__email='test@example.com](mailto:user__email='test@example.com)').exists()
```

## Testing Best Practices

### DO

- **Use factories**: Instead of manual object creation
- **One assertion per test**: Keep tests focused
- **Descriptive test names**: `test_user_cannot_delete_others_post`
- **Test edge cases**: Empty inputs, None values, boundary conditions
- **Mock external services**: Don't depend on external APIs
- **Use fixtures**: Eliminate duplication
- **Test permissions**: Ensure authorization works
- **Keep tests fast**: Use `--reuse-db` and `--nomigrations`

### DON'T

- **Don't test Django internals**: Trust Django to work
- **Don't test third-party code**: Trust libraries to work
- **Don't ignore failing tests**: All tests must pass
- **Don't make tests dependent**: Tests should run in any order
- **Don't over-mock**: Mock only external dependencies
- **Don't test private methods**: Test public interface
- **Don't use production database**: Always use test database

## Coverage

### Coverage Configuration

```bash
# Run tests with coverage
pytest --cov=apps --cov-report=html --cov-report=term-missing

# Generate HTML report
open htmlcov/index.html
```

### Coverage Goals

| Component | Target Coverage |
|-----------|-----------------|
| Models | 90%+ |
| Serializers | 85%+ |
| Views | 80%+ |
| Services | 90%+ |
| Utilities | 80%+ |
| Overall | 80%+ |

## Quick Reference

| Pattern | Usage |
|---------|-------|
| `@pytest.mark.django_db` | Enable database access |
| `client` | Django test client |
| `api_client` | DRF API client |
| `factory.create_batch(n)` | Create multiple objects |
| `patch('module.function')` | Mock external dependencies |
| `override_settings` | Temporarily change settings |
| `force_authenticate()` | Bypass authentication in tests |
| `assertRedirects` | Check for redirects |
| `assertTemplateUsed` | Verify template usage |
| `mail.outbox` | Check sent emails |

Remember: Tests are documentation. Good tests explain how your code should work. Keep them simple, readable, and maintainable.


  
