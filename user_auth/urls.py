from django.urls import path
from .views import AdminTokenObtainPairView, AdminTokenRefreshView, AdminLogoutView

urlpatterns = [
    path('login/', AdminTokenObtainPairView.as_view(), name='admin_login'),
    path('token/refresh/', AdminTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', AdminLogoutView.as_view(), name='admin_logout'),
]