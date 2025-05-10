import json
import uuid
from decimal import Decimal, ROUND_HALF_UP

import aiohttp
from loguru import logger
from typing import Optional, Tuple
from handlers.database import db
import aiosqlite
from datetime import datetime
from handlers.admin.admin_kb import get_admin_keyboard

def kop_to_rub(amount_kop: int) -> Decimal:
    return Decimal(amount_kop) / Decimal("100")

def clean_metadata(raw_meta: dict) -> dict:
    cleaned = {}
    for k, v in raw_meta.items():
        if v is None or str(v).lower() in {"none", "null"}:
            continue  # пропускаем недопустимые значения
        cleaned[str(k)[:32]] = str(v)[:512]  # ограничение по длине
    return cleaned

class PSPaymentsManager:
    def __init__(self):
        self.is_initialized = False

    async def init_yookassa(self) -> bool:
        """Инициализация PSPayments с настройками из базы данных"""
        try:
            settings = await db.get_pspayments_settings()
            if not settings or not settings[2] or not settings[3]:
                logger.error("PSPayments settings are not configured")
                return False

            self.shop_id = settings[2]
            self.secret_key = settings[4]
            self.is_initialized = True
            logger.info(f"PSPayments initialized with shop_id: {settings[2]}")
            return True

        except Exception as e:
            logger.error(f"Error initializing PSPayments: {e}")
            return False

    async def create_payment(self, amount: float, description: str, user_id: str = None,
                             tariff_name: str = None, username: str = None) -> Tuple[Optional[str], Optional[str]]:
        """Создает платеж в PSPayments и возвращает ID платежа и URL для оплаты"""
        if not self.is_initialized and not await self.init_yookassa():
            return None, None

        try:
            metadata = {
                "transaction_id": str(uuid.uuid4()),
                "telegram_id": str(user_id),
                "username": str(username)
            }

            decimal_rub = Decimal(str(amount))
            decimal_kop = (decimal_rub * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

            if "Пополнение баланса" in description:
                metadata["balance_payment"] = "true"
            elif tariff_name:
                metadata["tariff_name"] = tariff_name



            async with aiohttp.ClientSession() as session:
                sdata = {
                            "amount": int(decimal_kop),
                            "merchant_customer_id": f"tg_{user_id}",
                            "metadata": metadata
                        }
                logger.info(sdata)
                async with session.post(
                        f"https://api.p2p-paradise.info/payments",
                        headers={
                            'merchant-id': f"{self.shop_id}",
                            'merchant-secret-key': f"{self.secret_key}",
                        },
                        json=sdata
                ) as response:
                    status = response.status
                    text = await response.text()
                    logger.debug(f"[PSPayments] Статус ответа: {status}, Текст: {text}")

                    data = json.loads(text)
                    return f"psp_{data['uuid']}", data['redirect_url']

        except Exception as e:
            logger.error(f"Error creating PSPyaments payment: {e}")
            return None, None

    async def check_payment(self, payment_id: str, bot=None) -> bool:
        """Проверяет статус платежа"""
        if not self.is_initialized and not await self.init_yookassa():
            return False

        try:
            payment_id = payment_id.lstrip('psp_')

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"https://api.p2p-paradise.info/payments/{payment_id}",
                        headers={
                            'merchant-id': f"{self.shop_id}",
                            'merchant-secret-key': f"{self.secret_key}",
                        }
                ) as response:
                    status = response.status
                    text = await response.text()
                    logger.debug(f"[PSPayments] Статус ответа: {status}, Текст: {text}")
                    payment = json.loads(text)

            logger.info(f"Payment {payment['uuid']} status: {payment['status']}")

            if payment['status'] == 'success':
                logger.info(f"Payment {payment['uuid']} status: {payment['status']}")

                if payment['metadata'].get('balance_payment'):
                    from handlers.user.user_balance import process_successful_balance_payment
                    await process_successful_balance_payment(
                        payment_id=payment['uuid'],
                        amount=float(kop_to_rub(payment['amount'])),
                        user_id=int(payment['metadata'].get('telegram_id')),
                        bot=bot
                    )

                return True

        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            return False


pspayments_manager = PSPaymentsManager()