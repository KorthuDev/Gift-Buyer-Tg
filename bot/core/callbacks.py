import asyncio
from typing import Dict, Any

from pyrogram import Client

from app.notifications import send_notification
from app.purchase import buy_gift
from app.utils.logger import warn, info
from data.config import config, t


class GiftProcessor:
    @staticmethod
    async def evaluate_gift(gift_data: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        gift_price = gift_data.get("price", 0)
        is_limited = gift_data.get("is_limited", False)
        is_sold_out = gift_data.get("is_sold_out", False)
        is_upgradable = "upgrade_price" in gift_data
        total_amount = gift_data.get("total_amount", 0) if is_limited else 0

        exclusion_rules = {
            'sold_out': lambda: is_sold_out,
            'non_limited_blocked': lambda: not is_limited,
            'non_upgradable_blocked': lambda: config.PURCHASE_ONLY_UPGRADABLE_GIFTS and not is_upgradable
        }

        failed_rule = next((rule for rule, condition in exclusion_rules.items() if condition()), None)

        return (False, {'exclusion_reason': failed_rule}) if failed_rule else \
            GiftProcessor._evaluate_range_match(gift_price, total_amount)

    @staticmethod
    def _evaluate_range_match(gift_price: int, total_amount: int) -> tuple[bool, Dict[str, Any]]:
        range_matched, quantity, recipients = config.get_matching_range(gift_price, total_amount)
        return (True, {"quantity": quantity, "recipients": recipients}) if range_matched else (
            False, {
                "range_error": True,
                "gift_price": gift_price,
                "total_amount": total_amount
            }
        )


async def process_new_gift(app: Client, gift_data: Dict[str, Any]) -> None:
    gift_id = gift_data.get("id")

    is_eligible, processing_data = await GiftProcessor.evaluate_gift(gift_data)

    return await send_notification(app, gift_id, **processing_data) if not is_eligible and processing_data else \
        await _distribute_gifts(app, gift_id, processing_data.get("quantity", 1), processing_data.get("recipients", []))


async def _distribute_gifts(app: Client, gift_id: int, quantity: int, recipients: list) -> None:
    info(t("console.processing_gift", gift_id=gift_id, quantity=quantity, recipients_count=len(recipients)))

    for recipient_id in recipients:
        try:
            await buy_gift(app, recipient_id, gift_id, quantity)
        except Exception as ex:
            warn(t("console.purchase_error", gift_id=gift_id, chat_id=recipient_id))
            await send_notification(app, gift_id, error_message=str(ex))
        await asyncio.sleep(0.5)


process_gift = process_new_gift
