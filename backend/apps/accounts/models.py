from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user model. Roles/permissions and hospital membership are added in the RBAC stories."""
