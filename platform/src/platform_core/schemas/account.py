from pydantic import BaseModel, EmailStr, Field


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class ExportDataOut(BaseModel):
    ratings: list[dict]
    reviews: list[dict]
    lists: list[dict]
    notifications: list[dict]
