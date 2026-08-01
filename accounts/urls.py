from django.urls import path, reverse_lazy
from accounts.views import UserLoginView, UserSignupView, user_logout
from django.contrib.auth import views as auth_views

app_name = 'accounts'

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('signup/', UserSignupView.as_view(), name='signup'),
    path('logout/', user_logout, name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(success_url=reverse_lazy('accounts:password_reset_done')), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(success_url=reverse_lazy('accounts:password_reset_complete')), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
