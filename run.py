from __future__ import annotations

import os
import threading

import uvicorn

from admin_app import app
from main import VKBot


def run_bot() -> None:
    bot = VKBot()
    bot.start()


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, name="vk-bot", daemon=True)
    bot_thread.start()

    port = int(os.getenv("PORT", os.getenv("WEB_PORT", "3000")))
    uvicorn.run(app, host="0.0.0.0", port=port)
