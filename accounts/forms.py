from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.conf import settings

def get_client_ip(request):
    if not request:
        return '127.0.0.1'
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip

class LoginForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            User = get_user_model()
            # Case-insensitive lookup
            try:
                user = User.objects.get(username__iexact=username)
                username = user.username
                self.cleaned_data['username'] = username
            except User.DoesNotExist:
                pass

            # Rate limiting check
            ip = get_client_ip(self.request) if hasattr(self, 'request') else '127.0.0.1'
            lockout_key = f"login_lockout:{username.lower()}:{ip}"
            attempts_key = f"login_attempts:{username.lower()}:{ip}"

            if cache.get(lockout_key):
                raise ValidationError(
                    "Too many failed login attempts. Please try again later.",
                    code='lockout'
                )

            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                # Increment failed attempts
                attempts = cache.get(attempts_key, 0) + 1
                limit = getattr(settings, 'LOGIN_RATE_LIMIT_ATTEMPTS', 5)
                cooldown = getattr(settings, 'LOGIN_RATE_LIMIT_COOLDOWN', 300)
                if attempts >= limit:
                    cache.set(lockout_key, True, cooldown)
                    cache.delete(attempts_key)
                    raise ValidationError(
                        "Too many failed login attempts. Please try again later.",
                        code='lockout'
                    )
                else:
                    cache.set(attempts_key, attempts, cooldown)

                raise ValidationError(
                    "Please enter a correct username and password. Note that both fields may be case-sensitive.",
                    code='invalid_login',
                )
            else:
                self.confirm_login_allowed(self.user_cache)
                # Successful login clears rate limit records
                cache.delete(attempts_key)
                cache.delete(lockout_key)
        return self.cleaned_data

from django.contrib.auth.forms import UserCreationForm

class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    terms_accepted = forms.BooleanField(required=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "email")

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            User = get_user_model()
            # Case-insensitive duplicate check
            if User.objects.filter(username__iexact=username).exists():
                raise ValidationError(
                    "A user with that username already exists.",
                    code='duplicate_username'
                )
        return username
