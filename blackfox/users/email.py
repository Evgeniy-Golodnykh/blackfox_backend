from datetime import datetime as dt

from djoser import email

intro_activation_message = (
    'Cпасибо за регистрацию',
    'Вы изменили адрес электронной почты',
)
close_activation_message = (
    'Если вы не регистрировались',
    'Если вы не изменяли адрес электронной почты',
)
update_url = '/api/users/me'


class ActivationEmail(email.ActivationEmail):
    '''Override activation email with template.'''

    template_name = 'email/activation.html'

    def get_context_data(self):
        context = super().get_context_data()
        email_changed = update_url in self.request.path
        context['user_firstname'] = self.context.get('user').first_name
        context['intro_message'] = intro_activation_message[email_changed]
        context['close_message'] = close_activation_message[email_changed]
        context['year'] = dt.now().year
        return context


class PasswordResetEmail(email.PasswordResetEmail):
    '''Override reset password email with template.'''

    template_name = 'email/password_reset.html'

    def get_context_data(self):
        context = super().get_context_data()
        context['user_firstname'] = self.context.get('user').first_name
        context['year'] = dt.now().year
        return context
