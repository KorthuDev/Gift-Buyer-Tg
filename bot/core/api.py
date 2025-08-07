import configparser
import sys
from pathlib import Path
from typing import List, Union, Dict, Any

from app.utils.localization import localization
from app.utils.logger import error


class Config:
    def __init__(self):
        self.parser = configparser.ConfigParser()
        self._load_config()
        self._setup_paths()
        self._setup_properties()
        self._validate()
        localization.set_locale(self.LANGUAGE)

    def _load_config(self) -> None:
        config_file = Path('config.ini')
        config_file.exists() or self._exit_with_error("Configuration file 'config.ini' not found!")
        self.parser.read(config_file, encoding='utf-8')

    def _setup_paths(self) -> None:
        base_dir = Path(__file__).parent
        self.SESSION = str(base_dir.parent / "data/account")
        self.DATA_FILEPATH = base_dir / "json/history.json"

    def _setup_properties(self) -> None:
        self.API_ID = self.parser.getint('Telegram', 'API_ID', fallback=0)
        self.API_HASH = self.parser.get('Telegram', 'API_HASH', fallback='')
        self.PHONE_NUMBER = self.parser.get('Telegram', 'PHONE_NUMBER', fallback='')
        self.CHANNEL_ID = self._parse_channel_id()

        self.INTERVAL = self.parser.getfloat('Bot', 'INTERVAL', fallback=15.0)
        self.LANGUAGE = self.parser.get('Bot', 'LANGUAGE', fallback='EN').lower()
        self.HIDE_SENDER_NAME = self.parser.getboolean('Bot', 'HIDE_SENDER_NAME', fallback=True)

        self.GIFT_RANGES = self._parse_gift_ranges()
        self.PURCHASE_ONLY_UPGRADABLE_GIFTS = self.parser.getboolean('Gifts', 'PURCHASE_ONLY_UPGRADABLE_GIFTS',
                                                                     fallback=False)
        self.PRIORITIZE_LOW_SUPPLY = self.parser.getboolean('Gifts', 'PRIORITIZE_LOW_SUPPLY', fallback=False)

    def _parse_channel_id(self) -> Union[int, str, None]:
        channel_value = self.parser.get('Telegram', 'CHANNEL_ID', fallback='').strip()

        # TODO: Rewrite without using if-else blocks, like other functions

        if not channel_value or channel_value == '-100':
            return None

        if channel_value.startswith('@'):
            return channel_value

        if channel_value.startswith('-') and channel_value[1:].isdigit():
            return int(channel_value)

        if channel_value.isdigit():
            return int(channel_value)

        return f"@{channel_value}"

    def _parse_gift_ranges(self) -> List[Dict[str, Any]]:
        ranges_str = self.parser.get('Gifts', 'GIFT_RANGES', fallback='')
        ranges = []

        for range_item in ranges_str.split(';'):
            range_item = range_item.strip()
            range_item and ranges.append(self._parse_single_range(range_item))

        return [r for r in ranges if r]

    def _parse_single_range(self, range_item: str) -> Dict[str, Any]:
        try:
            price_part, rest = range_item.split(':', 1)
            supply_qty_part, recipients_part = rest.strip().split(':', 1)
            supply_part, quantity_part = supply_qty_part.strip().split(' x ')

            min_price, max_price = map(int, price_part.strip().split('-'))
            supply_limit = int(supply_part.strip())
            quantity = int(quantity_part.strip())
            recipients = self._parse_recipients_list(recipients_part.strip())

            return {
                'min_price': min_price,
                'max_price': max_price,
                'supply_limit': supply_limit,
                'quantity': quantity,
                'recipients': recipients
            }
        except (ValueError, IndexError):
            error(f"Invalid gift range format: {range_item}")
            return {}

    def _parse_recipients_list(self, recipients_str: str) -> List[Union[int, str]]:
        recipients = []

        for recipient in recipients_str.split(','):
            recipient = recipient.strip()
            recipient and recipients.append(self._parse_single_recipient(recipient))

        return [r for r in recipients if r is not None]

    def _parse_single_recipient(self, recipient: str) -> Union[int, str, None]:
        recipient_processors = {
            'username_with_at': {
                'condition': lambda uid: uid.startswith('@'),
                'handler': lambda uid: uid[1:]
            },
            'numeric_id': {
                'condition': lambda uid: uid.isdigit(),
                'handler': lambda uid: int(uid)
            },
            'username_without_at': {
                'condition': lambda: True,
                'handler': lambda uid: uid
            }
        }

        return self._process_with_handlers(recipient, recipient_processors)

    @staticmethod
    def _process_with_handlers(value: str, processors: Dict) -> Any:
        for processor in processors.values():
            condition_func = processor['condition']
            try:
                condition_result = condition_func(value) if callable(condition_func) else condition_func()
                condition_result and processor['handler'](value) if 'handler' in processor else processor['handler']()
                return processor['handler'](value) if condition_result and 'handler' in processor else (
                    processor['handler']() if condition_result else None)
            except (ValueError, TypeError):
                continue
        return None

    def get_matching_range(self, price: int, total_amount: int) -> tuple[bool, int, List[Union[int, str]]]:
        matching_ranges = [
            (range_config['quantity'], range_config['recipients'])
            for range_config in self.GIFT_RANGES
            if (range_config['min_price'] <= price <= range_config['max_price'] and
                total_amount <= range_config['supply_limit'])
        ]

        return (True, *matching_ranges[0]) if matching_ranges else (False, 0, [])

    def _validate(self) -> None:
        validation_rules = {
            "Telegram > API_ID": lambda: self.API_ID == 0,
            "Telegram > API_HASH": lambda: not self.API_HASH,
            "Telegram > PHONE_NUMBER": lambda: not self.PHONE_NUMBER,
            "Gifts > GIFT_RANGES": lambda: not self.GIFT_RANGES,
        }

        invalid_fields = [field for field, check in validation_rules.items() if check()]
        invalid_fields and self._exit_with_validation_error(invalid_fields)

    @staticmethod
    def _exit_with_error(message: str) -> None:
        error(message)
        sys.exit(1)

    def _exit_with_validation_error(self, invalid_fields: List[str]) -> None:
        error_msg = localization.translate("errors.missing_config").format(
            '\n'.join(f'- {field}' for field in invalid_fields))
        self._exit_with_error(error_msg)

    @property
    def language_display(self) -> str:
        return localization.get_display_name(self.LANGUAGE)

    @property
    def language_code(self) -> str:
        return localization.get_language_code(self.LANGUAGE)


config = Config()
t = localization.translate
get_language_display = localization.get_display_name
get_language_code = localization.get_language_code
