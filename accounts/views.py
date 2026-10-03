from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.http import HttpResponse
from accounts.forms import LoginForm, SignupForm

class UserLoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        form = LoginForm()
        try:
            return render(request, 'accounts/login.html', {'form': form})
        except Exception:
            form_html = f"<form method='post'>{form.as_p()}<button type='submit'>Login</button></form>"
            return HttpResponse(form_html)

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            request.session.pop('guest_search_count', None)
            request.session.pop('show_auth_modal', None)
            next_url = request.GET.get('next') or request.POST.get('next') or 'home'
            from django.utils.http import url_has_allowed_host_and_scheme
            if not url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                next_url = 'home'
            return redirect(next_url)
        try:
            return render(request, 'accounts/login.html', {'form': form})
        except Exception:
            form_html = f"<form method='post'>{form.as_p()}<button type='submit'>Login</button></form>"
            return HttpResponse(form_html)

class UserSignupView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        form = SignupForm()
        try:
            return render(request, 'accounts/signup.html', {'form': form})
        except Exception:
            form_html = f"<form method='post'>{form.as_p()}<button type='submit'>Sign Up</button></form>"
            return HttpResponse(form_html)

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            request.session.pop('guest_search_count', None)
            request.session.pop('show_auth_modal', None)
            next_url = request.GET.get('next') or request.POST.get('next') or 'home'
            from django.utils.http import url_has_allowed_host_and_scheme
            if not url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                next_url = 'home'
            return redirect(next_url)
        try:
            return render(request, 'accounts/signup.html', {'form': form})
        except Exception:
            form_html = f"<form method='post'>{form.as_p()}<button type='submit'>Sign Up</button></form>"
            return HttpResponse(form_html)

def user_logout(request):
    auth_logout(request)
    return redirect('home')

