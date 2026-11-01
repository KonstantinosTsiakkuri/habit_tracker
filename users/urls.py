from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.apps import UsersConfig
from users.views import MeView, RegisterView

app_name = UsersConfig.name

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
]
