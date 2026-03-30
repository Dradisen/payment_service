from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderPaymentStatus, PaymentStatus, PaymentType
from app.models.payment import Payment
from app.repositories.order import OrderRepository
from app.repositories.payment import PaymentRepository
from app.services.bank_client import BankAPIClient, bank_client
from app.exceptions.bank import BankPaymentNotFoundError
from app.services.payment_strategies import PaymentStrategyFactory

from app.exceptions.payment import (
    OrderNotFoundError,
    PaymentNotFoundError,
    OrderAlreadyPaidError,
    InsufficientOrderBalanceError,
    InvalidPaymentStatusError,
    NotAcquiringPaymentError,
)


class PaymentService:
    """Бизнес-сервис по работе с платежами"""
    
    def __init__(self,
        order_repo: OrderRepository,
        payment_repo: PaymentRepository,
        bank: BankAPIClient = bank_client,
    ) -> None:
        self._orders = order_repo
        self._payments = payment_repo
        self._bank = bank

    async def deposit(
        self,
        order_id: int,
        amount: int,
        payment_type: PaymentType,
        session: AsyncSession,
    ) -> Payment:
        """Создайть новый платеж и выполнить внесение средств по заказу"""
        
        order = await self._orders.get(order_id)
        if order is None:
            raise OrderNotFoundError(f"Заказ {order_id} не найден")

        if order.payment_status == OrderPaymentStatus.PAID:
            raise OrderAlreadyPaidError(f"Заказ {order_id} оплачен")

        paid_for_pending = await self._payments.paid_for_pending(order_id)
        paid_so_far = await self._payments.paid(order_id)
        remaining = order.amount - paid_so_far - paid_for_pending

        if amount > remaining:
            raise InsufficientOrderBalanceError(
                f"Сумма {amount} превышает оставшийся баланс {remaining}"
            )

        payment = Payment(
            order_id=order_id,
            payment_type=payment_type,
            amount=amount,
            status=PaymentStatus.PENDING,
        )
        
        await self._payments.save(payment)

        strategy = PaymentStrategyFactory.get(payment_type, bank=self._bank)
        await strategy.deposit(payment, session)
        
        return payment

    async def refund(self, payment_id: int, session: AsyncSession) -> Payment:
        """Возврат средств за уже произведенный платеж и повторная синхронизация статуса заказа."""
        payment = await self._payments.get(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Платеж {payment_id} не найден")

        if payment.status != PaymentStatus.COMPLETED:
            raise InvalidPaymentStatusError(
                f"Возврат возможен только для платежей в статусе COMPLETED, текущий статус: {payment.status}"
            )

        strategy = PaymentStrategyFactory.get(payment.payment_type, bank=self._bank)
        await strategy.refund(payment, session)
        return payment

    async def sync_acquiring(
        self, payment_id: int, session: AsyncSession
    ) -> tuple[Payment, bool, str]:
        """
        Синхронизировать статус эквайринг-платежа с банком.
        """
        payment = await self._payments.get(payment_id)

        if payment is None:
            raise PaymentNotFoundError(f"Платеж {payment_id} не найден")

        if payment.payment_type != PaymentType.ACQUIRING:
            raise NotAcquiringPaymentError(
                f"Платеж {payment_id} не является платежом эквайринга"
            )

        detail = payment.acquiring_detail
        if detail is None or detail.bank_payment_id is None:
            return payment, False, "Нет идентификатора банковского платежа"
        
        try:
            bank_resp = await self._bank.check_acquiring(detail.bank_payment_id)
        except BankPaymentNotFoundError:
            return payment, False, "Платеж не найден"
        
        detail.bank_status = bank_resp.status
        detail.bank_amount = bank_resp.amount
        detail.bank_paid_at = bank_resp.paid_at
        detail.synced_at = datetime.now(timezone.utc)
        session.add(detail)

        synced = False
        bank_status_lower = bank_resp.status.lower()

        if bank_status_lower in ("paid", "completed", "success") and payment.status != PaymentStatus.COMPLETED:
            payment.amount = bank_resp.amount
            payment.status = PaymentStatus.COMPLETED
            synced = True
        elif bank_status_lower in ("refunded", "reversed") and payment.status != PaymentStatus.REFUNDED:
            payment.amount = bank_resp.amount
            payment.status = PaymentStatus.REFUNDED
            synced = True
        message = f"Ствтус: {bank_resp.status}"
        return payment, synced, message

    # async def _sync_order_status(self, order: Order, session: AsyncSession) -> None:
    #     """Recompute and persist order.payment_status based on completed payment sums."""
    #     await self._payments.paid(order.id)
