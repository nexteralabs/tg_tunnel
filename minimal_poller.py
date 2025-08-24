# quick_poll_test.py
import os, asyncio
from telegram.ext import Application, MessageHandler, filters

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def echo(update, context):
    print("UPDATE:", update.effective_chat.id, "->", update.effective_message.text)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True, allowed_updates=["message","callback_query"])
    print("Polling… send a message to the bot.")
    try:
        await asyncio.sleep(30)  # listen for 30s
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

asyncio.run(main())