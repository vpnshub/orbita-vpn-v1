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
                "telegram_id": user_id,
                "username": username
            }

            decimal_rub = Decimal(str(amount))
            decimal_kop = (decimal_rub * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

            if "Пополнение баланса" in description:
                metadata["balance_payment"] = "true"
            elif tariff_name:
                metadata["tariff_name"] = tariff_name

            logger.info({
                            "amount": f"{decimal_kop}",
                            "merchant_customer_id": f"tg_{user_id}",
                            "metadata": json.dumps(metadata)
                        })

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"https://api.p2p-paradise.info/payments",
                        headers={
                            'merchant-id': f"{self.shop_id}",
                            'merchant-secret-key': f"{self.secret_key}",
                        },
                        data={
                            "amount": f"{decimal_kop}",
                            "merchant_customer_id": f"tg_{user_id}",
                            "metadata": json.dumps(metadata)
                        }
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
                else:
                    if bot:
                        async with aiosqlite.connect(db.db_path) as conn:
                            async with conn.execute(
                                    'SELECT pay_notify FROM bot_settings LIMIT 1'
                            ) as cursor:
                                notify_settings = await cursor.fetchone()

                            if notify_settings and notify_settings[0] != 0:
                                message_text = (
                                    "🎉 Новая подписка! 🏆\n"
                                    "<blockquote>"
                                    f"👤 Пользователь: {payment['metadata'].get('telegram_id')}\n"
                                    f"💳 Тариф: {payment['metadata'].get('tariff_name')}\n"
                                    f"📅 Дата активации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                                    "🚀 Подписка успешно оформлена!</blockquote>"
                                )

                                try:
                                    await bot.send_message(
                                        chat_id=notify_settings[0],
                                        text=message_text,
                                        parse_mode="HTML",
                                        # reply_markup=get_admin_keyboard()
                                    )
                                except Exception as e:
                                    logger.error(f"Ошибка при отправке уведомления о подписке: {e}")

                return True

        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            return False


pspayments_manager = PSPaymentsManager()