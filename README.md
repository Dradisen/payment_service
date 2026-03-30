# Сервис работы с платежами по заказу

Проект реализует сервис управления платежами для заказов с поддержкой:

Эквайринг с банком реализован в тестах, по причине того, что это внешний сервис. 
В АПИ реализован рабочий вариант с наличными

## Стурктура
```
|-api/ - вьюхи
|-conf/ - конфигурация проекта
|-core/ - ядро
|-exceptions/ - исключения
|-models/ - модели
|-repositories/ - репозитории
|-schemas/ - сериализаторы
|-services/ - бизнес-логика
|-tests/ - тесты
```

## компоненты

- `app/services/payment_service.py` — бизнес-логика создания платежей и возвратов
- `app/services/bank_client.py` — HTTP-клиент для общения с банком-эквайером
- `app/models/payment.py` — модель платежа и связь с заказом
- `tests/test_payments.py` — интеграционные тесты с PostgreSQL

## Запуск

```
docker compose run --rm migrate
docker compose up
```

## Запуск тестов

Проект собрал в docker-compose. Тесты запускаются через Docker Compose и используют PostgreSQL для обкатки:

```bash
docker compose run --rm test
```

| Функция | Описание |
|---------|----------|
| `test_cash_deposit_cash_completed` | Проверка депозита наличными, чистый кейс |
| `test_cash_deposit_partially_paid` | Проверка оплаты частичного заказа наличными |
| `test_cash_deposit_updates_order_to_paid` | Проверка перевода заказа в статус PAID после полной оплаты |
| `test_cash_deposit_few_partially_paid` | Проверка нескольких частичных оплат заказа наличными |
| `test_cash_deposit_few_partially_underpaid` | Проверка нескольких частичных оплат заказа наличными c переплатой |
| `test_deposit_raises_if_order_not_found` | Проверка ошибки при попытке оплатить несуществующий заказ |
| `test_deposit_raises_if_order_already_paid` | Проверка ошибки при попытке оплатить уже полностью оплаченный заказ |
| `test_cash_sync_acquiring_raises_for_non_acquiring_payment` | Проверка ошибки при попытке синхронизировать неэквайринговый платеж |
| `test_refund_cash_sets_refunded` | Возврат наличного платежа |
| `test_acquiring_deposit_cash_completed` | Проверка депозита эквайрингом, чистый кейс |
| `test_deposit_partially_paid` | Проверка оплаты частичного заказа эквайрингом |
| `test_deposit_over_create_acquiring` | Проверка создания платежа эквайрингом с суммой больше, чем остаток по заказу |
| `test_deposit_unexpected_payment` | Тест на неожиданные изменения при депозите эквайрингом |
| `test_deposit_uncorrect_status_acquiring` | Проверка некорректного ответа от банка |
| `test_sync_acquiring_raises_if_payment_not_found` | Несуществующий платеж при синхронизации с банком |
| `test_deposit_refund_processing_acquiring` | Проверка возврата платежа эквайрингом с обрабатываемым статусом в банке |
| `test_refund_raises_if_payment_not_found` | Проверка ошибки при попытке вернуть несуществующий платеж |

## Схема базы

![image](./images/image.png)

В качестве денежных средств выбрано поле INT, а по хорошему лучше BIGINT

Нет ошибок округления
Быстрее вычисления
Проще агрегаты

В данном кейсе считаю это уместным решением. В таком ответе возвращают платежные системы Юмани и АТОЛ.онлайн, что улучшает интеграцию.
Но не подходит в биллинге, где могут расчеты вычисляться до 6-7 знаком после запятой. Например в расходах на LLM токены