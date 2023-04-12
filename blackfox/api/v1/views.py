from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsAdmin
from .serializers import (
    ChangePasswordSerializer, LoginSerializer, MeSerializer, SignUpSerializer,
    UserSerializer,
)

User = get_user_model()


class GetPatchView(generics.UpdateAPIView, generics.RetrieveAPIView):
    """Get/Patch mix View."""


class UserViewSet(viewsets.ModelViewSet):
    """A viewset to read and edit User instances."""

    queryset = User.objects.all()
    lookup_field = 'username'
    serializer_class = UserSerializer
    permission_classes = (IsAdmin,)


class SignUpView(generics.CreateAPIView):
    """User registration view."""

    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = SignUpSerializer


class LoginView(TokenObtainPairView):
    """User login view."""

    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer


class MeView(GetPatchView):
    """A view to read and edit own profile."""

    queryset = User.objects.all()
    serializer_class = MeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    http_method_names = ('get', 'patch')

    def get(self, request):
        resp = MeSerializer(request.user, context=request).data
        return Response(resp, status=status.HTTP_200_OK)

    def partial_update(self, request):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.update(request.user, serializer.validated_data)
        resp = MeSerializer(request.user).data
        return Response(resp, status=status.HTTP_200_OK)


class ChangePasswordView(generics.UpdateAPIView):
    """A view to change User password."""

    queryset = User.objects.all()
    serializer_class = ChangePasswordSerializer
    permission_classes = (permissions.IsAuthenticated,)
    http_method_names = ('put')

    def update(self, request):
        user = self.request.user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                'Old password does not match.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response(
            'Password updated successfully.', status=status.HTTP_200_OK
        )
