"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from .views import health_check, trigger_500, HomeView, set_theme

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('trigger-500/', trigger_500, name='trigger_500'),
    path('set-theme/', set_theme, name='set_theme'),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('analytics/', include('analytics.urls')),
    path('endpoints/', include('endpoints.urls')),
    path('', HomeView.as_view(), name='home'),
]

handler404 = 'config.views.custom_error_404'
handler500 = 'config.views.custom_error_500'
