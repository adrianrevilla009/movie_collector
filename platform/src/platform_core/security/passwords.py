"""Hashing y politica de contrasenas (Seccion 2.4): argon2id + zxcvbn."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from zxcvbn import zxcvbn

_hasher = PasswordHasher()

MIN_LENGTH = 10
MIN_ZXCVBN_SCORE = 2  # 0-4; 2 = "razonablemente resistente" sin ser prohibitivo


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


class WeakPasswordError(ValueError):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def validate_password_strength(plain: str, user_inputs: list[str] | None = None) -> None:
    """Lanza WeakPasswordError si la contrasena no cumple la politica minima.
    No se usan reglas de composicion arbitrarias (mayus/minus/numero), que
    producen contrasenas debiles en la practica (Seccion 2.4) - se usa zxcvbn."""
    reasons = []
    if len(plain) < MIN_LENGTH:
        reasons.append(f"La contrasena debe tener al menos {MIN_LENGTH} caracteres")

    result = zxcvbn(plain, user_inputs=user_inputs or [])
    if result["score"] < MIN_ZXCVBN_SCORE:
        reasons.append("La contrasena es demasiado predecible o comun")

    if reasons:
        raise WeakPasswordError(reasons)
