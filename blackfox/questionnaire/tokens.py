import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

CLAIM_TOKEN_LIFETIME = timedelta(days=30)


def hash_claim_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_claim_token():
    """A one-time token plus what to store: its hash and expiry."""

    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + CLAIM_TOKEN_LIFETIME
    return token, hash_claim_token(token), expires_at
