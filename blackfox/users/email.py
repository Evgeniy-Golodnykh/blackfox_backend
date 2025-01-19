import datetime

from django.contrib.auth import get_user_model
from djoser import email

User = get_user_model()


class ActivationEmail(email.ActivationEmail):
    '''Override activation email with template.'''

    template_name = 'email/activation.html'


class PasswordResetEmail(email.PasswordResetEmail):
    '''Override reset password email with template.'''

    template_name = 'email/password_reset.html'


def email_context_processor(request):
    if not hasattr(request, 'data'):
        return {}
    email = request.data.get('email')
    return {
        'first_name': User.objects.filter(email=email).first().first_name,
        'year': datetime.datetime.now().year
    } if email else {}
