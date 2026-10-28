from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr

from app.api.deps import get_current_user, get_current_active_superuser
from app.core import mail
from app.schema.user import Message


router = APIRouter(prefix="/utils", tags=["utils"])

@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
async def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    await mail.send_email(template="test_email", to=email_to, data={"email": email_to})
    return Message(message="Test email queued")


@router.get("/health-check/")
async def health_check() -> bool:
    return True