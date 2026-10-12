from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Role, User
from .services import email_in_use, split_full_name

PHONE_REGEX = r"^\+?[\d\s-]{7,20}$"


class LoginSerializer(serializers.Serializer):
    # Limits stop oversized input before the password hasher runs on it (LOGIN-N14).
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, max_length=512)


class SignupSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=300)
    email = serializers.EmailField()
    phone = serializers.RegexField(PHONE_REGEX, required=False, allow_blank=True, default="")
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_email(self, value):
        if email_in_use(value):
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        first, last = split_full_name(attrs["full_name"])
        candidate = User(email=attrs["email"], username=attrs["email"], first_name=first, last_name=last)
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


def hospital_ref(user):
    return {"id": user.hospital_id, "name": user.hospital.name} if user.hospital_id else None


class UserSerializer(serializers.ModelSerializer):
    fullName = serializers.SerializerMethodField()
    role = serializers.CharField(source="effective_role")
    isStaff = serializers.BooleanField(source="is_hospital_staff")
    hospital = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "fullName", "phone", "role", "isStaff", "hospital"]

    def get_fullName(self, user):
        return user.get_full_name() or user.email

    def get_hospital(self, user):
        return hospital_ref(user)


class UserSummarySerializer(serializers.ModelSerializer):
    """A row of the admin's user list (UserSummary in docs/architecture/api-contracts.md)."""

    fullName = serializers.SerializerMethodField()
    role = serializers.CharField(source="effective_role")
    hospital = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source="is_active")
    roleLocked = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "fullName", "role", "hospital", "isActive", "roleLocked"]

    def get_fullName(self, user):
        return user.get_full_name() or user.email

    def get_hospital(self, user):
        return hospital_ref(user)

    def get_roleLocked(self, user):
        return user.is_superuser or user.pk == self.context["request"].user.pk


class RoleChangeSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
