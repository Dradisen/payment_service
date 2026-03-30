
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.repositories.order import OrderRepository
from app.repositories.payment import PaymentRepository
from app.services.payment_service import PaymentService


def payment_service(session: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(
        order_repo=OrderRepository(session),
        payment_repo=PaymentRepository(session),
    )