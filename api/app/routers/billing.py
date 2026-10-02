from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.billing import CheckoutRequest, CheckoutResponse, PlanOut, PortalResponse
from app.schemas.common import MessageResponse
from app.services import billing

router = APIRouter(prefix="/billing", tags=["billing"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/plans", response_model=list[PlanOut])
async def list_plans() -> list[PlanOut]:
    return [PlanOut(**p) for p in billing.list_plans()]


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    return CheckoutResponse(checkout_url=await billing.create_checkout(db, user, body.tier))


@router.post("/portal", response_model=PortalResponse)
async def portal(user: User = Depends(get_current_user)) -> PortalResponse:
    return PortalResponse(portal_url=await billing.create_portal(user))


@webhook_router.post("/stripe", response_model=MessageResponse)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    payload = await request.body()
    event = billing.verify_event(payload, request.headers.get("stripe-signature"))
    return MessageResponse(status=await billing.handle_event(db, event))
