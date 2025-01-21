from datetime import datetime as dt

from django.contrib.auth import get_user_model
from djoser import email

User = get_user_model()
intro_message = (
    'Cпасибо за регистрацию',
    'Вы изменили адрес электронной почты'
)
close_message = (
    'Если вы не регистрировались',
    'Если вы не изменяли адрес электронной почты'
)


class ActivationEmail(email.ActivationEmail):
    '''Override activation email with template.'''

    template_name = 'email/activation.html'


class PasswordResetEmail(email.PasswordResetEmail):
    '''Override reset password email with template.'''

    template_name = 'email/password_reset.html'


def email_context_processor(request):
    if not hasattr(request, 'data') or not request.data.get('email'):
        return {}
    current_date = dt.now()
    user = User.objects.filter(email=request.data.get('email')).first()
    email_changed = current_date.date() > user.date_joined.date()
    return {
        'user_firstname': user.first_name,
        'intro_message': intro_message[email_changed],
        'close_message': close_message[email_changed],
        'year': current_date.year,
    }
