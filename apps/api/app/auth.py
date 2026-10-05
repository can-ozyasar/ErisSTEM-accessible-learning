"""Geliştirme kimlik doğrulaması için emniyetli sınır.

Üretimde bu bağımlılık OIDC doğrulanmış claim'leriyle değiştirilmelidir.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Annotated

from fastapi import Header, HTTPException


class Role(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    REVIEWER = "reviewer"
    ADMIN = "admin"


def require_roles(*roles: Role):
    def dependency(x_role: Annotated[str | None, Header()] = None) -> Role:
        if os.getenv("APP_ENV", "development") == "production":
            raise HTTPException(
                status_code=503,
                detail="OIDC kimlik doğrulaması yapılandırılmadan üretim API'si açılamaz",
            )
        if x_role is None:
            raise HTTPException(status_code=401, detail="Kimlik doğrulama gerekli")
        try:
            role = Role(x_role)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Geçersiz rol") from exc
        if role not in roles:
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        return role

    return dependency
