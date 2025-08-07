from pyrogram import Client
from pyrogram.errors import RPCError

from app.errors import handle_gift_error
from app.notifications import send_notification
from app.utils.helper import get_recipient_info, get_user_balance
from app.utils.logger import info, warn
from data.config import t, config

class GiftPurchaser:
    @staticmethod
    async def buy_gift(app: Client, chat_id: int, gift_id: int, quantity: int = 1) -> None:
        recipient_info, username = await get_recipient_info(app, chat_id)
        gift_price = await GiftPurchaser._get_gift_price(app, gift_id)
        current_balance = await get_user_balance(app)

        max_affordable = min(quantity, current_balance // gift_price) if gift_price > 0 else quantity

        max_affordable == 0 and await GiftPurchaser._handle_insufficient_balance(
            app, gift_id, gift_price, current_balance, quantity)

        await GiftPurchaser._purchase_gifts(app, chat_id, gift_id, max_affordable, recipient_info, username)

        max_affordable < quantity and await GiftPurchaser._notify_partial_purchase(
            app, gift_id, quantity, max_affordable, gift_price, current_balance)

    @staticmethod
    async def _get_gift_price(app: Client, gift_id: int) -> int:
        try:
            gifts = await app.get_available_gifts()
            return next((gift.price for gift in gifts if gift.id == gift_id), 0)
        except Exception:
            return 0

    @staticmethod
    async def _purchase_gifts(app: Client, chat_id: int, gift_id: int, quantity: int,
                              recipient_info: str, username: str) -> None:
        for i in range(quantity):
            current_gift = i + 1
            try:
                await app.send_gift(chat_id=chat_id, gift_id=gift_id, hide_my_name=config.HIDE_SENDER_NAME)
                info(t("console.gift_sent", current=current_gift, total=quantity,
                          gift_id=gift_id, recipient=recipient_info))
                await send_notification(app, gift_id, user_id=chat_id, username=username,
                                        current_gift=current_gift, total_gifts=quantity,
                                        success_message=True)
            except RPCError as ex:
                current_balance = await get_user_balance(app)
                await handle_gift_error(app, ex, gift_id, chat_id,
                                        await GiftPurchaser._get_gift_price(app, gift_id), current_balance)
                break

    @staticmethod
    async def _handle_insufficient_balance(app: Client, gift_id: int, gift_price: int, current_balance: int,
                                           requested_quantity: int) -> None:
        warn(t("console.insufficient_balance_for_quantity",
               gift_id=gift_id, requested=requested_quantity,
               price=gift_price, balance=current_balance))
        await send_notification(app, gift_id,
                                balance_error=True,
                                gift_price=gift_price * requested_quantity,
                                current_balance=current_balance)

    @staticmethod
    async def _notify_partial_purchase(app: Client, gift_id: int, requested: int,
                                       purchased: int, gift_price: int, remaining_balance: int) -> None:
        warn(t("console.partial_purchase",
               gift_id=gift_id, purchased=purchased, requested=requested,
               remaining_needed=(requested - purchased) * gift_price,
               current_balance=remaining_balance))
        await send_notification(app, gift_id,
                                partial_purchase=True,
                                purchased=purchased,
                                requested=requested,
                                remaining_cost=(requested - purchased) * gift_price,
                                current_balance=remaining_balance)


buy_gift = GiftPurchaser.buy_gift
