from django.urls import path

from tgbot.views import (
    MyNotificationsView, MyTelegramView, TelegramLinkCodeView,
    TelegramLoginView, TelegramTestMessageView, TelegramWebhookView,
)

urlpatterns = [
    path('auth/telegram/', TelegramLoginView.as_view(),
         name='telegram-login'),
    path('users/me/telegram/', MyTelegramView.as_view(),
         name='telegram-me'),
    path('users/me/notifications/', MyNotificationsView.as_view(),
         name='notifications-me'),
    path('users/me/telegram/test/', TelegramTestMessageView.as_view(),
         name='telegram-test'),
    path('users/me/telegram/link/', TelegramLinkCodeView.as_view(),
         name='telegram-link-code'),
    path('telegram/webhook/', TelegramWebhookView.as_view(),
         name='telegram-webhook'),
]
