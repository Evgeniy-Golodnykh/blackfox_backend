from django.urls import path

from tgbot.views import (
    MyTelegramView, TelegramLinkCodeView, TelegramLoginView,
    TelegramWebhookView,
)

urlpatterns = [
    path('auth/telegram/', TelegramLoginView.as_view(),
         name='telegram-login'),
    path('users/me/telegram/', MyTelegramView.as_view(),
         name='telegram-me'),
    path('users/me/telegram/link/', TelegramLinkCodeView.as_view(),
         name='telegram-link-code'),
    path('telegram/webhook/', TelegramWebhookView.as_view(),
         name='telegram-webhook'),
]
