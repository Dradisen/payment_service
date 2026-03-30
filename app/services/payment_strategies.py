from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentStatus
from app.models.payment import AcquiringDetail, Payment
from app.models.enums import PaymentType
from app.services.bank_client import BankAPIClient, bank_client


class PaymentStrategy(Protocol):
    async def deposit(self, payment: Payment, session: AsyncSession) -> None: ...
    async def refund(self, payment: Payment, session: AsyncSession) -> None: ...


class CashPaymentStrategy:
    """Оплата наличными"""

    async def deposit(self, payment: Payment, session: AsyncSession) -> None:
        payment.status = PaymentStatus.COMPLETED

    async def refund(self, payment: Payment, session: AsyncSession) -> None:
        payment.status = PaymentStatus.REFUNDED


class AcquiringPaymentStrategy:
    """Оплата эквайрингом"""

    def __init__(self, client: BankAPIClient) -> None:
        self._client = client

    async def deposit(self, payment: Payment, session: AsyncSession) -> None:
        """Пополнение"""
        bank_resp = await self._client.start_acquiring(payment.order_id, payment.amount)
        detail = AcquiringDetail(
            payment_id=payment.id,
            bank_payment_id=bank_resp.bank_payment_id,
            synced_at=datetime.now(timezone.utc),
        )
        session.add(detail)

    async def refund(self, payment: Payment, session: AsyncSession) -> None:
        """Возврат"""
        payment.status = PaymentStatus.REFUNDED


class PaymentStrategyFactory:
    
    @staticmethod
    def get(payment_type: PaymentType, bank: BankAPIClient = bank_client) -> PaymentStrategy:
        if payment_type == PaymentType.CASH:
            return CashPaymentStrategy()
        if payment_type == PaymentType.ACQUIRING:
            return AcquiringPaymentStrategy(client=bank)
        raise ValueError(f"Неизвестный тип платежного метода: {payment_type}")
