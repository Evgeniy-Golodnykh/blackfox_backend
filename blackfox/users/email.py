from djoser import email


class ActivationEmail(email.ActivationEmail):
    '''Override activation email with template.'''

    template_name = 'email/activation.html'


class PasswordResetEmail(email.PasswordResetEmail):
    '''Override reset password email with template.'''

    template_name = 'email/password_reset.html'
