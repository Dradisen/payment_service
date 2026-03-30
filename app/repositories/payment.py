from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import PaymentStatus, PaymentType
from app.models.payment import AcquiringDetail, Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, payment_id: int) -> Payment | None:
        result = await self._session.execute(
            select(Payment)
            .where(Payment.id == payment_id)
            .options(selectinload(Payment.acquiring_detail))
        )
        return result.scalar_one_or_none()

    async def list_by_order(self, order_id: int) -> list[Payment]:
        """Список заказов"""
        result = await self._session.execute(
            select(Payment)
            .where(Payment.order_id == order_id)
            .options(selectinload(Payment.acquiring_detail))
            .order_by(Payment.created_at)
        )
        return list(result.scalars().all())

    async def list_pending_acquiring(self) -> list[Payment]:
        """Список платежей ожидающих эквайринга"""
        result = await self._session.execute(
            select(Payment)
            .where(
                Payment.status == PaymentStatus.PENDING,
                Payment.payment_type == PaymentType.ACQUIRING,
            )
            .options(selectinload(Payment.acquiring_detail))
        )
        return list(result.scalars().all())

    async def paid(self, order_id: int) -> int:
        """Оплачено"""
        result = await self._session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.COMPLETED,
            )
        )
        return int(str(result.scalar()))

    async def paid_for_pending(self, order_id: int) -> int:
        """Ожидающие оплаты"""
        result = await self._session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.PENDING,
            )
        )
        return int(str(result.scalar()))
    
    async def save(self, payment: Payment) -> Payment:
        self._session.add(payment)
        await self._session.flush()
        await self._session.refresh(payment)
        return payment

    async def save_acquiring_detail(self, detail: AcquiringDetail) -> AcquiringDetail:
        self._session.add(detail)
        await self._session.flush()
        return detail
