from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    vk_group_token: str
    vk_group_id: str
    vk_mode: str
    bitrix_webhook_url: str
    openai_api_key: str
    openai_model: str
    portfolio_url: str
    company_name: str
    db_path: str


def get_settings() -> Settings:
    return Settings(
        vk_group_token=os.getenv("VK_GROUP_TOKEN", ""),
        vk_group_id=os.getenv("VK_GROUP_ID", ""),
        vk_mode=os.getenv("VK_MODE", "longpoll"),
        bitrix_webhook_url=os.getenv("BITRIX_WEBHOOK_URL", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        portfolio_url=os.getenv("PORTFOLIO_URL", "https://example.com"),
        company_name=os.getenv("COMPANY_NAME", "Interinc"),
        db_path=os.getenv("DB_PATH", "bot.db"),
    )
