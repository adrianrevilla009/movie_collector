"""Seed de un unico usuario admin (Seccion 2.4): "un unico usuario admin creado
por seed en Fase 0.2 (no hay flujo de auto-registro como admin)".

Gap detectado en la revision de Fase 0: no existia ningun comando real para
crear el primer admin, solo se hacia a mano en tests promoviendo el rol
directamente en la base de datos. Este script es la forma reproducible de
bootstrapear un admin en un entorno nuevo (dev o CI).

Uso (sin argumentos, usa ADMIN_EMAIL/ADMIN_PASSWORD/ADMIN_NAME de .env):
    uv run --package platform-core python -m platform_core.scripts.seed_admin

Uso (con overrides explicitos):
    uv run --package platform-core python -m platform_core.scripts.seed_admin \\
        --email otro@admin.local --password "OtraClaveFuerte123!" --name "Otro Admin"

Idempotente: si el email ya existe, solo se promueve a role=admin y se marca
email_verified=True (no falla si se ejecuta dos veces, util en `make ingest`/CI).
"""

import argparse
import asyncio

from sqlalchemy import select

from platform_core.config import get_settings
from platform_core.db import async_session_factory, engine
from platform_core.models import User, UserRole
from platform_core.security.passwords import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
)


async def seed_admin(email: str, password: str, name: str) -> None:
    try:
        validate_password_strength(password, user_inputs=[email, name])
    except WeakPasswordError as exc:
        raise SystemExit(f"Contrasena de admin demasiado debil: {'; '.join(exc.reasons)}") from exc

    try:
        async with async_session_factory() as db:
            existing = await db.scalar(select(User).where(User.email == email))
            if existing is not None:
                existing.role = UserRole.admin
                existing.email_verified = True
                await db.commit()
                print(f"Usuario existente '{email}' promovido a admin.")
                return

            user = User(
                email=email,
                name=name,
                password_hash=hash_password(password),
                role=UserRole.admin,
                # el admin de seed no pasa por el flujo de verificacion por email
                email_verified=True,
            )
            db.add(user)
            await db.commit()
            print(f"Admin '{email}' creado.")
    finally:
        # Cierra explicitamente el pool de conexiones ANTES de que
        # asyncio.run() cierre el event loop. Sin esto, en Windows
        # (ProactorEventLoop) la conexion asyncpg pooled intenta limpiarse a
        # si misma despues de que el loop ya esta cerrado y el script termina
        # con un traceback "Event loop is closed" / "'NoneType' object has no
        # attribute 'send'" aunque el seed ya se haya guardado correctamente.
        await engine.dispose()


def main() -> None:
    # Los defaults vienen de Settings (pydantic-settings, lee .env de forma
    # identica en Windows/Mac/Linux) en vez de exigir que el Makefile/la
    # shell propaguen variables de entorno - eso fallaba en Windows, donde
    # `make` invoca cmd.exe por defecto (no entiende `set -a`/`. ./.env`).
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Seed del usuario admin (Seccion 2.4)")
    parser.add_argument("--email", default=settings.admin_email)
    parser.add_argument("--password", default=settings.admin_password)
    parser.add_argument("--name", default=settings.admin_name)
    args = parser.parse_args()
    asyncio.run(seed_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
