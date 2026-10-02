from app.schemas.common import RequestModel, ResponseModel, Tier


class PlanOut(ResponseModel):
    tier: str
    name: str
    tier_label: str
    badge: str
    price_cents: int
    interval: str
    trial_days: int
    features: list[str]


class CheckoutRequest(RequestModel):
    tier: Tier


class CheckoutResponse(ResponseModel):
    checkout_url: str


class PortalResponse(ResponseModel):
    portal_url: str
