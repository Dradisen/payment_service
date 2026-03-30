import os
import pytest

from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.conf.base import config
from app.models.base import Base
from app.models.enums import OrderPaymentStatus, PaymentStatus, PaymentType
from app.models.order import Order
from app.models.payment import Payment
from app.services.bank_client import BankAPIClient
from app.repositories.order import OrderRepository
from app.repositories.payment import PaymentRepository
from app.exceptions.bank import BankError, BankValidationError
from app.services.payment_service import (
    InsufficientOrderBalanceError,
    InvalidPaymentStatusError,
    NotAcquiringPaymentError,
    OrderAlreadyPaidError,
    OrderNotFoundError,
    PaymentNotFoundError,
    PaymentService,
)


@pytest.fixture
async def test_engine():
    database_url = os.getenv("TEST_DATABASE_URL") or config.DATABASE_URL
    url = make_url(database_url)

    if not (url.database and url.database.endswith("_test")):
        raise RuntimeError(
            "Используйте базу данных для тестов с именем, оканчивающимся на '_test'"
        )

    engine = create_async_engine(
        database_url,
        echo=config.DEBUG,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    AsyncSessionMaker = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        future=True,
    )

    async with AsyncSessionMaker() as session:
        yield session


async def create_order(order_repo: OrderRepository, amount: int = 100000) -> Order:
    order = Order(amount=amount)
    await order_repo.save(order)
    return order

# ============================================================================
# Тесты депозита наличными
# ============================================================================


@pytest.mark.asyncio
async def test_cash_deposit_cash_completed(db_session: AsyncSession):
    """Проверка депозита наличными, чистый кейс"""
    
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo, payment_repo)

    order = await create_order(order_repo, amount=100000)
    payment = await service.deposit(
        order_id=order.id, 
        amount=100000, 
        payment_type=PaymentType.CASH, 
        session=db_session
    )
    await order_repo.save(order)

    assert payment.status == PaymentStatus.COMPLETED
    assert payment.amount == 100000
    assert order.payment_status == OrderPaymentStatus.PAID

@pytest.mark.asyncio
async def test_cash_deposit_partially_paid(db_session: AsyncSession):
    """Проверка оплаты частичного заказа наличными"""
    
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    order = await create_order(order_repo, amount=50000)

    payment = await service.deposit(
        order_id=order.id,
        amount=20000,
        payment_type=PaymentType.CASH,
        session=db_session,
    )
    await order_repo.save(order)
    
    assert payment.status == PaymentStatus.COMPLETED
    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID

@pytest.mark.asyncio
async def test_cash_deposit_updates_order_to_paid(db_session: AsyncSession):
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    order = await create_order(order_repo, amount=50000)

    await service.deposit(
        order_id=order.id,
        amount=50000,
        payment_type=PaymentType.CASH,
        session=db_session,
    )
    await order_repo.save(order)
    assert order.payment_status == OrderPaymentStatus.PAID

@pytest.mark.asyncio
async def test_cash_deposit_few_partially_paid(db_session: AsyncSession):
    """Проверка нескольких частичных оплат заказа наличными"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    order = await create_order(order_repo, amount=50000)

    payment = await service.deposit(
        order_id=order.id,
        amount=20000,
        payment_type=PaymentType.CASH,
        session=db_session,
    )
    assert payment.amount == 20000
    assert payment.status == PaymentStatus.COMPLETED

    await db_session.refresh(order)
    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID

    await service.deposit(
        order_id=order.id,
        amount=30000,
        payment_type=PaymentType.CASH,
        session=db_session,
    )

    await db_session.refresh(order)
    assert order.payment_status == OrderPaymentStatus.PAID

@pytest.mark.asyncio
async def test_cash_deposit_few_partially_underpaid(db_session: AsyncSession):
    """Проверка нескольких частичных оплат заказа наличными c переплатой"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    order = await create_order(order_repo, amount=50000)

    payment = await service.deposit(
        order_id=order.id,
        amount=20000,
        payment_type=PaymentType.CASH,
        session=db_session,
    )
    assert payment.status == PaymentStatus.COMPLETED

    with pytest.raises(InsufficientOrderBalanceError):
        await service.deposit(
            order_id=order.id,
            amount=40000,
            payment_type=PaymentType.CASH,
            session=db_session,
        )

@pytest.mark.asyncio
async def test_deposit_raises_if_order_not_found(db_session: AsyncSession):
    """Проверка ошибки при попытке оплатить несуществующий заказ"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    with pytest.raises(OrderNotFoundError):
        await service.deposit(
            order_id=123,
            amount=1000,
            payment_type=PaymentType.CASH,
            session=db_session,
        )

@pytest.mark.asyncio
async def test_deposit_raises_if_order_already_paid(db_session: AsyncSession):
    """Проверка ошибки при попытке оплатить уже полностью оплаченный заказ"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    order = await create_order(order_repo, amount=20000)

    payment = await service.deposit(
        order_id=order.id,
        amount=20000,
        payment_type=PaymentType.CASH,
        session=db_session,
    )

    assert payment.status == PaymentStatus.COMPLETED
    await db_session.refresh(order)

    assert order.payment_status == OrderPaymentStatus.PAID
    
    with pytest.raises(OrderAlreadyPaidError):
        await service.deposit(
            order_id=order.id,
            amount=20000,
            payment_type=PaymentType.CASH,
            session=db_session,
        )
        
@pytest.mark.asyncio
async def test_cash_sync_acquiring_raises_for_non_acquiring_payment(db_session):
    """Проверка ошибки при попытке синхронизировать неэквайринговый платеж"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    order = await create_order(order_repo)
    payment = Payment(
        order_id=order.id,
        amount=10000,
        payment_type=PaymentType.CASH,
        status=PaymentStatus.COMPLETED,
    )
    await payment_repo.save(payment)

    with pytest.raises(NotAcquiringPaymentError):
        await service.sync_acquiring(payment_id=payment.id, session=db_session)

@pytest.mark.asyncio
async def test_refund_cash_sets_refunded(db_session: AsyncSession):
    """Возврат наличного платежа"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    order = await create_order(order_repo, amount=10000)
    payment = await service.deposit(
        order_id=order.id,
        amount=10000,
        payment_type=PaymentType.CASH,
        session=db_session,
    )
    await db_session.refresh(order)
    assert order.payment_status == OrderPaymentStatus.PAID
    
    result = await service.refund(payment_id=payment.id, session=db_session)
    await db_session.refresh(order)
    
    assert result.status == PaymentStatus.REFUNDED
    assert order.payment_status == OrderPaymentStatus.UNPAID


# ---------------------------------------------------------------------------
# Тесты c оплатой эквайринга
# ---------------------------------------------------------------------------

def prepare_mock_bank_api(response: dict) -> AsyncMock:
    mock_response = MagicMock()
    mock_response.json.return_value = response
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_client
    mock_context.__aexit__.return_value = None
    return mock_context

@pytest.mark.asyncio
async def test_acquiring_deposit_cash_completed(db_session: AsyncSession):
    """Проверка депозита эквайрингом, чистый кейс"""
    
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo, payment_repo)

    order = await create_order(order_repo, amount=100000)

    mock_context = prepare_mock_bank_api({"bank_payment_id": "123"})

    with patch.object(BankAPIClient, "_client", return_value=mock_context):
        payment = await service.deposit(
            order_id=order.id, 
            amount=100000,
            payment_type=PaymentType.ACQUIRING, 
            session=db_session
        )

    assert payment.status == PaymentStatus.PENDING
    assert payment.amount == 100000
    
    await db_session.refresh(order)
    await db_session.refresh(payment)
    
    assert order.payment_status == OrderPaymentStatus.UNPAID
    
    mock_context = prepare_mock_bank_api({
        "bank_payment_id": "123", 
        "status": "completed", 
        "amount": 100000, 
        "paid_at": datetime.now(timezone.utc).isoformat()
    })
    
    with patch.object(BankAPIClient, "_client", return_value=mock_context):
        payment, is_sync, _ = await service.sync_acquiring(
            payment_id=payment.id,
            session=db_session
        )
    await db_session.flush()
    await db_session.refresh(order)
    
    assert is_sync == True
    assert payment.status == PaymentStatus.COMPLETED
    assert order.payment_status == OrderPaymentStatus.PAID
       
@pytest.mark.asyncio
async def test_deposit_partially_paid(db_session: AsyncSession):
    """Проверка оплаты частичного заказа эквайрингом"""

    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo, payment_repo)

    order = await create_order(order_repo, amount=200000)
    
    mock_data_payment_1 = prepare_mock_bank_api({"bank_payment_id": "some-1"})
    with patch.object(BankAPIClient, "_client", return_value=mock_data_payment_1):
        payment1 =await service.deposit(
            order_id=order.id, 
            amount=100000,
            payment_type=PaymentType.ACQUIRING, 
            session=db_session
        )

    mock_data_payment_2 = prepare_mock_bank_api({"bank_payment_id": "some-2"})
    with patch.object(BankAPIClient, "_client", return_value=mock_data_payment_2):
        payment2 = await service.deposit(
            order_id=order.id, 
            amount=100000,
            payment_type=PaymentType.ACQUIRING, 
            session=db_session
        )

    assert (
        payment1.status == PaymentStatus.PENDING and \
        payment2.status == PaymentStatus.PENDING
    )

    await db_session.refresh(order)
    await db_session.refresh(payment1)
    await db_session.refresh(payment2)
    
    assert order.payment_status == OrderPaymentStatus.UNPAID
    
    mock_data_check_1 = prepare_mock_bank_api({
        "bank_payment_id": "some-1",
        "status": "paid",
        "amount": 100000,
        "paid_at": datetime.now(timezone.utc).isoformat()
    })
    
    mock_data_check_2 = prepare_mock_bank_api({
        "bank_payment_id": "some-2",
        "status": "paid",
        "amount": 100000,
        "paid_at": datetime.now(timezone.utc).isoformat()
    })
    
    with patch.object(BankAPIClient, "_client", return_value=mock_data_check_1):
        payment1, is_sync_1, _ = await service.sync_acquiring(
            payment_id=payment1.id,
            session=db_session
        )
    
    assert is_sync_1 == True
    assert payment1.status == PaymentStatus.COMPLETED
    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID
    
    with patch.object(BankAPIClient, "_client", return_value=mock_data_check_2):
        payment2, is_sync_2, _ = await service.sync_acquiring(
            payment_id=payment2.id,
            session=db_session
        )

    assert is_sync_2 == True
    assert payment2.status == PaymentStatus.COMPLETED
    assert order.payment_status == OrderPaymentStatus.PAID

@pytest.mark.asyncio
async def test_deposit_over_create_acquiring(db_session: AsyncSession):
    """Проверка создания платежа эквайрингом с суммой больше, чем остаток по заказу"""

    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo, payment_repo)

    order = await create_order(order_repo, amount=200000)
    
    mock_payment_1 = prepare_mock_bank_api({"bank_payment_id": "111"})
    mock_payment_2 = prepare_mock_bank_api({"bank_payment_id": "222"})
    mock_payment_3 = prepare_mock_bank_api({"bank_payment_id": "333"})
    
    with patch.object(BankAPIClient, "_client", return_value=mock_payment_1):
        payment1 = await service.deposit(
            order_id=order.id, 
            amount=100000,
            payment_type=PaymentType.ACQUIRING, 
            session=db_session
        )

    with patch.object(BankAPIClient, "_client", return_value=mock_payment_2):
        payment2 = await service.deposit(
            order_id=order.id, 
            amount=100000,
            payment_type=PaymentType.ACQUIRING, 
            session=db_session
        )

    assert (
        payment1.status == PaymentStatus.PENDING and \
        payment2.status == PaymentStatus.PENDING
    )

    await db_session.refresh(order)
    await db_session.refresh(payment1)
    await db_session.refresh(payment2)
    
    assert order.payment_status == OrderPaymentStatus.UNPAID
    
    with patch.object(BankAPIClient, "_client", return_value=mock_payment_3):
        with pytest.raises(InsufficientOrderBalanceError):    
            await service.deposit(
                order_id=order.id, 
                amount=100000,
                payment_type=PaymentType.ACQUIRING, 
                session=db_session
            )

@pytest.mark.asyncio
async def test_deposit_unexpected_payment(db_session: AsyncSession):
    """Тест на неожиданные изменения при депозите эквайрингом"""

    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo, payment_repo)

    order = await create_order(order_repo, amount=200000)
    
    mock_payment = prepare_mock_bank_api({
        "bank_rename_attribute_id": "1231",
    })    
    with patch.object(BankAPIClient, "_client", return_value=mock_payment):
        with pytest.raises(BankError):    
            await service.deposit(
                order_id=order.id, 
                amount=100000,
                payment_type=PaymentType.ACQUIRING, 
                session=db_session
            )

@pytest.mark.asyncio
async def test_deposit_uncorrect_status_acquiring(db_session: AsyncSession):
    """Проверка некорректного ответа от банка"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo, payment_repo)

    order = await create_order(order_repo, amount=200000)
    
    mock_payment = prepare_mock_bank_api({
        "bank_payment_id": False,
    })
    with patch.object(BankAPIClient, "_client", return_value=mock_payment):
        with pytest.raises(BankValidationError):
            await service.deposit(
                order_id=order.id, 
                amount=100000,
                payment_type=PaymentType.ACQUIRING, 
                session=db_session
            )

@pytest.mark.asyncio
async def test_sync_acquiring_raises_if_payment_not_found(db_session: AsyncSession):
    """Несуществующий платеж при синхронизации с банком"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)
    
    with pytest.raises(PaymentNotFoundError):
        await service.sync_acquiring(payment_id=1, session=db_session)

@pytest.mark.asyncio
async def test_deposit_refund_processing_acquiring(db_session: AsyncSession):
    """Проверка возврата платежа эквайрингом с обрабатываемым статусом в банке"""
    
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo, payment_repo)

    order = await create_order(order_repo, amount=200000)
    
    mock_payment = prepare_mock_bank_api({
        "bank_payment_id": '213',
    })
    with patch.object(BankAPIClient, "_client", return_value=mock_payment):
        payment = await service.deposit(
            order_id=order.id, 
            amount=200000,
            payment_type=PaymentType.ACQUIRING, 
            session=db_session
        )
    
    await db_session.refresh(order)
    assert order.payment_status == OrderPaymentStatus.UNPAID
    assert payment.status == PaymentStatus.PENDING
    
    with pytest.raises(InvalidPaymentStatusError):
        await service.refund(payment_id=payment.id, session=db_session)

@pytest.mark.asyncio
async def test_refund_raises_if_payment_not_found(db_session):
    """Проверка ошибки при попытке вернуть несуществующий платеж"""
    order_repo = OrderRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    service = PaymentService(order_repo=order_repo, payment_repo=payment_repo)

    with pytest.raises(PaymentNotFoundError):
        await service.refund(payment_id=1, session=db_session)