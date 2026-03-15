from django.contrib.auth.backends import ModelBackend

from .models import TicketsUser


class EmailBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        if email is None:
            return None

        try:
            user = TicketsUser.objects.get(email=email)
            if user.check_password(password) and self.user_can_authenticate(
                user
            ):
                return user
        except TicketsUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return TicketsUser.objects.get(pk=user_id)
        except TicketsUser.DoesNotExist:
            return None
