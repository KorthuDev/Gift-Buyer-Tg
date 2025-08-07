import aiohttp
import logging
from aiogram import Bot, types
from utils.logger import log
from config import load_config

config = load_config()


class GiftsApi:
    """A class to interact with Telegram Bot API for gift-related operations."""

    def __init__(self):
        """Initialize the GiftsApi with bot token from config."""
        self.bot_token: str = config['bot_token']

    async def aio_get_available_gifts(self, session: aiohttp.ClientSession) -> list | None:
        """
        Fetch available gifts from Telegram API asynchronously.

        Args:
            session: An active aiohttp ClientSession for making HTTP requests

        Returns:
            list: A list of available gifts if successful
            None: If the request fails or API returns error

        Note:
            Uses Telegram Bot API method: /getAvailableGifts
        """
        url = f"https://api.telegram.org/bot{self.bot_token}/getAvailableGifts"
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                if data.get('ok') is True:
                    return data.get('result', {}).get('gifts', [])
                else:
                    log.error(f"API response error: {data}")
                    return None
        except Exception as e:
            log.error(f"Error while requesting /getAvailableGifts: {e}")
            return None

    async def aio_get_file_path(self, file_id: str) -> str | None:
        """
        Get the file path from Telegram servers by file ID.

        Args:
            file_id: Telegram file identifier string

        Returns:
            str: File path if successful
            None: If the request fails or file not found

        Note:
            Uses Telegram Bot API method: /getFile
        """
        url = f"https://api.telegram.org/bot{self.bot_token}/getFile?file_id={file_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if data.get('ok'):
                        return data['result']['file_path']
                    else:
                        log.error(
                            f"API response error while getting file path: {data}")
                        return None
        except Exception as e:
            log.error(f"Error while requesting file path: {e}")
            return None

    async def download_file(self, file_path: str) -> bytes | None:
        """
        Download file content from Telegram servers.

        Args:
            file_path: Path to the file on Telegram servers

        Returns:
            bytes: File content if download successful
            None: If download fails

        Raises:
            ValueError: If server returns non-200 status code
        """
        download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    else:
                        raise ValueError(
                            f"File download error: status {resp.status}")
        except Exception as e:
            log.error(f"File download error: {e}")
            return None

    async def send_thumbnail_photo(self, bot: Bot, chat_id: int, thumb_file_id: str, caption: str) -> None:
        """
        Send thumbnail photo to specified chat with fallback to document.

        Args:
            bot: Initialized aiogram Bot instance
            chat_id: Target chat ID
            thumb_file_id: Telegram file ID of the thumbnail
            caption: Message caption to include with the file

        Behavior:
            1. First attempts to send as photo
            2. On failure, attempts to send as document
            3. On complete failure, sends error message with caption
        """
        # Get file path
        file_path = await self.aio_get_file_path(thumb_file_id)
        if not file_path:
            await bot.send_message(chat_id, f"(Failed to get thumbnail) {caption}")
            return

        # Download file content
        file_content = await self.download_file(file_path)
        if not file_content:
            await bot.send_message(chat_id, f"(Failed to download thumbnail) {caption}")
            return

        # Send file as photo
        input_photo = types.BufferedInputFile(
            file_content, filename="gift_thumb.webp")
        try:
            await bot.send_photo(chat_id, photo=input_photo, caption=caption)
        except Exception as e:
            log.warning(
                f"Failed to send as photo, trying as document. Error: {e}")
            try:
                input_document = types.BufferedInputFile(
                    file_content, filename="gift_thumb.webp")
                await bot.send_document(chat_id, document=input_document, caption=caption)
            except Exception as doc_e:
                log.error(f"Failed to send as document: {doc_e}")

    async def send_gift(self, user_id: int, gift_id: str, pay_for_upgrade: bool = False) -> bool:
        """
        Send a Telegram gift to specified user.

        Args:
            user_id: Recipient's Telegram user ID
            gift_id: Identifier of the gift to send
            pay_for_upgrade: Whether bot should pay for gift upgrade (default: False)

        Returns:
            bool: True if gift was sent successfully, False otherwise

        Note:
            Uses Telegram Bot API method: /sendGift
        """
        url = f"https://api.telegram.org/bot{self.bot_token}/sendGift"
        payload = {
            "user_id": user_id,
            "gift_id": gift_id,
            "pay_for_upgrade": pay_for_upgrade,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return True
                    else:
                        log.error(
                            f"Gift sending error: {data.get('description')}")
                        return False
        except Exception as e:
            log.error(f"Error while requesting sendGift: {e}")
            return False
