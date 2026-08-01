from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

PLATFORM_CHOICES = [
    ('amazon', 'Amazon'),
    ('flipkart', 'Flipkart'),
    ('croma', 'Croma'),
    ('reliance', 'Reliance Digital'),
]

class SearchQueryManager(models.Manager):
    def recent_for_user(self, user, limit=20):
        if not user or user.is_anonymous:
            return self.none()
        return self.filter(user=user).order_by('-timestamp')[:limit]

class SearchQuery(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    query = models.CharField(max_length=255)
    session_key = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    result_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    source = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=255, default='India')
    failure_reason = models.CharField(max_length=255, null=True, blank=True)

    objects = SearchQueryManager()

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return self.query

    def mark_completed(self, result_count):
        self.status = 'completed'
        self.result_count = result_count
        self.save(update_fields=['status', 'result_count'])

    def mark_failed(self, reason=None):
        self.status = 'failed'
        self.failure_reason = reason
        self.save(update_fields=['status', 'failure_reason'])


class ProductResultManager(models.Manager):
    def for_search(self, search):
        return self.filter(search=search).order_by('price')

class ProductResult(models.Model):
    search = models.ForeignKey(
        SearchQuery,
        related_name="results",
        on_delete=models.CASCADE
    )
    platform = models.CharField(max_length=50, db_index=True)
    title = models.CharField(max_length=500)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    price_str = models.CharField(max_length=100, null=True, blank=True)
    image_url = models.URLField(max_length=1000, null=True, blank=True)
    product_url = models.URLField(max_length=1000)
    rating = models.CharField(max_length=50, null=True, blank=True)
    raw_data = models.JSONField(null=True, blank=True)
    is_real_data = models.BooleanField(default=True)
    fetched_at = models.DateTimeField(default=timezone.now)
    category = models.CharField(max_length=255, null=True, blank=True)

    objects = ProductResultManager()

    def __str__(self):
        return f"{self.title} - {self.platform}"

    def clean(self):
        super().clean()
        # Price validation
        if self.price is not None and self.price < 0:
            raise ValidationError({'price': 'Price cannot be negative.'})

        # URL spaces self-healing
        if self.product_url:
            self.product_url = self.product_url.replace(' ', '%20')
        if self.image_url:
            self.image_url = self.image_url.replace(' ', '%20')

        # URL validation
        validator = URLValidator()
        try:
            validator(self.product_url)
        except ValidationError:
            raise ValidationError({'product_url': 'Invalid product URL.'})

        # Platform validation
        if not self.platform or not self.platform.strip():
            raise ValidationError({'platform': "Platform cannot be empty."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
