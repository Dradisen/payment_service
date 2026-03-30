from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, order_id: int) -> Order | None:
        result = await self._session.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.payments))
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[Order]:
        result = await self._session.execute(
            select(Order).options(selectinload(Order.payments)).order_by(Order.created_at)
        )
        return list(result.scalars().all())

    async def save(self, order: Order) -> Order:
        self._session.add(order)
        await self._session.flush()
        await self._session.refresh(order)
        return order
