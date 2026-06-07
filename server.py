from run import run_bot
from admin_app import app

import os
import threading

import uvicorn


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, name="vk-bot", daemon=True)
    bot_thread.start()

    port = int(os.getenv("PORT", os.getenv("WEB_PORT", "3000")))
    uvicorn.run(app, host="0.0.0.0", port=port)
