from django.test import TestCase, override_settings
from django.core.cache import cache
from accounts.apps import AccountsConfig

class AppConfigTests(TestCase):
    def test_app_config_imports_without_error(self):
        self.assertEqual(AccountsConfig.name, 'accounts')

from accounts.forms import LoginForm
from django.contrib.auth import get_user_model

class LoginFormTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='TestUser', password='password123')

    def test_valid_login_exact_case(self):
        form = LoginForm(data={'username': 'TestUser', 'password': 'password123'})
        self.assertTrue(form.is_valid())

    def test_valid_login_case_insensitive(self):
        form = LoginForm(data={'username': 'testuser', 'password': 'password123'})
        self.assertTrue(form.is_valid())

    def test_invalid_login_wrong_password(self):
        form = LoginForm(data={'username': 'TestUser', 'password': 'wrongpassword'})
        self.assertFalse(form.is_valid())
        # Check custom error message is in form non-field errors
        self.assertIn("Please enter a correct username and password", form.errors['__all__'][0])

    def test_invalid_login_empty_fields(self):
        form = LoginForm(data={'username': '', 'password': ''})
        self.assertFalse(form.is_valid())

from accounts.forms import SignupForm

class SignupFormTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='ExistingUser', password='password123', email='exist@example.com')

    def test_valid_signup(self):
        form = SignupForm(data={
            'username': 'NewUser',
            'email': 'new@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'terms_accepted': True
        })
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.username, 'NewUser')
        self.assertEqual(user.email, 'new@example.com')

    def test_duplicate_username_case_insensitive(self):
        form = SignupForm(data={
            'username': 'existinguser',
            'email': 'different@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'terms_accepted': True
        })
        self.assertFalse(form.is_valid())
        self.assertIn("A user with that username already exists.", form.errors['username'][0])

    def test_terms_not_accepted(self):
        form = SignupForm(data={
            'username': 'AnotherUser',
            'email': 'another@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'terms_accepted': False
        })
        self.assertFalse(form.is_valid())

from django.urls import reverse

class UserLoginViewTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='TestUser', password='password123')

    def test_login_get(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_login_post_success(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'TestUser',
            'password': 'password123'
        })
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)

    def test_login_post_fail(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'TestUser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")

    def test_login_redirect_when_authenticated(self):
        self.client.login(username='TestUser', password='password123')
        response = self.client.get(reverse('accounts:login'))
        self.assertRedirects(response, reverse('home'))

class UserSignupViewTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='ExistingUser', password='password123', email='exist@example.com')

    def test_signup_get(self):
        response = self.client.get(reverse('accounts:signup'))
        self.assertEqual(response.status_code, 200)

    def test_signup_post_success(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'NewUser',
            'email': 'new@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'terms_accepted': True
        })
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(self.User.objects.filter(username='NewUser').count(), 1)
        new_user = self.User.objects.get(username='NewUser')
        self.assertEqual(int(self.client.session['_auth_user_id']), new_user.id)

    def test_signup_post_mismatched_passwords(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'NewUser2',
            'email': 'new2@example.com',
            'password1': 'StrongPass123!',
            'password2': 'WrongPass123!',
            'terms_accepted': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.User.objects.filter(username='NewUser2').count(), 0)

    def test_signup_post_duplicate_username(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'existinguser',
            'email': 'different@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'terms_accepted': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists.")

    def test_signup_redirect_when_authenticated(self):
        self.client.login(username='ExistingUser', password='password123')
        response = self.client.get(reverse('accounts:signup'))
        self.assertRedirects(response, reverse('home'))

class UserLogoutViewTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='TestUser', password='password123')

    def test_logout_redirects_and_clears_auth(self):
        self.client.login(username='TestUser', password='password123')
        # Check that we are logged in
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)
        
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('home'))
        
        # Check that we are logged out
        self.assertNotIn('_auth_user_id', self.client.session)

from django.core import mail

class PasswordResetTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='TestUser', password='password123', email='test@example.com')

    def test_password_reset_flow(self):
        # 1. Post to password reset view
        response = self.client.post(reverse('accounts:password_reset'), {
            'email': 'test@example.com'
        })
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        
        # Verify email is sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('test@example.com', email.to)
        
        # 2. Extract reset link parameters from email body
        body = email.body
        import re
        link_match = re.search(r'/accounts/password-reset-confirm/([^/]+)/([^/]+)/', body)
        self.assertTrue(link_match, "Password reset link not found in email body")
        uidb64 = link_match.group(1)
        token = link_match.group(2)
        
        # 3. Access confirmation page (following redirect to the token-less view)
        confirm_url = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        response = self.client.get(confirm_url, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Get the redirected URL (e.g. /accounts/password-reset-confirm/Mw/set-password/)
        set_password_url = response.request['PATH_INFO']
        
        # 4. Set new password by posting to the set-password url
        response = self.client.post(set_password_url, {
            'new_password1': 'NewSecurePassword123!',
            'new_password2': 'NewSecurePassword123!'
        })
        self.assertRedirects(response, reverse('accounts:password_reset_complete'))
        
        # 5. Verify user can log in with new password
        login_response = self.client.post(reverse('accounts:login'), {
            'username': 'TestUser',
            'password': 'NewSecurePassword123!'
        })
        self.assertRedirects(login_response, reverse('home'))

class GuestSearchLimitMiddlewareTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='TestUser', password='password123')

    @override_settings(GUEST_SEARCH_LIMIT=2)
    def test_guest_search_limits(self):
        # 1. First anonymous POST
        response = self.client.post(reverse('products:search'), {'query': 'test'})
        self.assertEqual(self.client.session.get('guest_search_count'), 1)
        self.assertFalse(self.client.session.get('show_auth_modal'))

        # 2. Second anonymous POST (should reach the limit of 2)
        response = self.client.post(reverse('products:search'), {'query': 'test'})
        self.assertEqual(self.client.session.get('guest_search_count'), 2)
        self.assertTrue(self.client.session.get('show_auth_modal'))

        # 3. Third anonymous POST
        response = self.client.post(reverse('products:search'), {'query': 'test'})
        self.assertEqual(self.client.session.get('guest_search_count'), 3)
        self.assertTrue(self.client.session.get('show_auth_modal'))

    @override_settings(GUEST_SEARCH_LIMIT=2)
    def test_authenticated_user_search_does_not_increment_limit(self):
        self.client.login(username='TestUser', password='password123')
        response = self.client.post(reverse('products:search'), {'query': 'test'})
        self.assertNotIn('guest_search_count', self.client.session)
        self.assertNotIn('show_auth_modal', self.client.session)

    @override_settings(GUEST_SEARCH_LIMIT=2)
    def test_session_cleanup_on_auth_login(self):
        self.client.post(reverse('products:search'), {'query': 'test'})
        self.client.post(reverse('products:search'), {'query': 'test'})
        self.assertEqual(self.client.session.get('guest_search_count'), 2)
        self.assertTrue(self.client.session.get('show_auth_modal'))

        response = self.client.post(reverse('accounts:login'), {
            'username': 'TestUser',
            'password': 'password123'
        })
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('guest_search_count', self.client.session)
        self.assertNotIn('show_auth_modal', self.client.session)

    @override_settings(GUEST_SEARCH_LIMIT=2)
    def test_session_cleanup_on_auth_signup(self):
        self.client.post(reverse('products:search'), {'query': 'test'})
        self.assertEqual(self.client.session.get('guest_search_count'), 1)

        response = self.client.post(reverse('accounts:signup'), {
            'username': 'NewUserSignUp',
            'email': 'newsignup@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'terms_accepted': True
        })
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('guest_search_count', self.client.session)
        self.assertNotIn('show_auth_modal', self.client.session)

class ProtectedRouteTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='AuthUser', password='password123')

    def test_history_anonymous_redirects(self):
        url = reverse('products:history')
        response = self.client.get(url)
        # Should redirect to login with next parameter
        login_url = reverse('accounts:login')
        self.assertRedirects(response, f"{login_url}?next={url}")

    def test_history_authenticated_succeeds(self):
        self.client.login(username='AuthUser', password='password123')
        response = self.client.get(reverse('products:history'))
        self.assertEqual(response.status_code, 200)

class LoginRateLimitTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='RateLimitedUser', password='password123')
        cache.clear()

    @override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=3, LOGIN_RATE_LIMIT_COOLDOWN=60)
    def test_login_rate_limiting_lockout_and_cooldown(self):
        for _ in range(2):
            response = self.client.post(reverse('accounts:login'), {
                'username': 'RateLimitedUser',
                'password': 'wrongpassword'
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Please enter a correct username and password")

        response = self.client.post(reverse('accounts:login'), {
            'username': 'RateLimitedUser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed login attempts")

        response = self.client.post(reverse('accounts:login'), {
            'username': 'RateLimitedUser',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed login attempts")

        cache.clear()

        response = self.client.post(reverse('accounts:login'), {
            'username': 'RateLimitedUser',
            'password': 'password123'
        })
        self.assertRedirects(response, reverse('home'))









