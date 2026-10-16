import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    REQUIRED_FIELDS = ['email']

    @property
    def role_name(self):
        group = self.groups.order_by('name').first()
        return group.name.replace('People Pulse ', '') if group else 'User'
