import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_dummy_hash = _hasher.hash("dummy-password-for-unmatched-login")


def hash_password(password: str):
    return _hasher.hash(password)


def verify_password(password: str, encoded: str | None):
    try:
        verified = _hasher.verify(encoded or _dummy_hash, password)
        return bool(encoded and verified)
    except (VerificationError, InvalidHashError):
        return False


def token_hash(token: str):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token():
    return secrets.token_urlsafe(32)
