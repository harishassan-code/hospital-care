from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, SignupSerializer, UserSerializer
from .services import EmailTaken, authenticate_by_email, register_patient

INVALID_CREDENTIALS = {"detail": "That email and password don't match an account."}


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """GET once on app start so the `csrftoken` cookie exists before the first POST."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(INVALID_CREDENTIALS, status=status.HTTP_400_BAD_REQUEST)
        user = authenticate_by_email(request, **serializer.validated_data)
        if user is None:
            # Same message whether the email exists or not, so accounts can't be discovered.
            return Response(INVALID_CREDENTIALS, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = register_patient(**serializer.validated_data)
        except EmailTaken:
            return Response({"email": ["An account with this email already exists."]}, status=409)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """Who is signed in. 403 when nobody is, which the frontend treats as 'show the login page'."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
