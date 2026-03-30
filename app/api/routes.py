

from fastapi import APIRouter

from app.api.v1 import orders, payments

router_v1 = APIRouter(prefix="/v1")
router_v1.include_router(orders.router)
router_v1.include_router(payments.router)