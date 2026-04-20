
import asyncio
from telegram import Bot, Update, InlineKeyboardButton, CopyTextButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import bot_token
import logging

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    user_name = update.effective_user.name

    keyboard = [
        [
            InlineKeyboardButton(text="کپی کردن آیدی عددی من",copy_text=CopyTextButton(text=str(user_id))),
            InlineKeyboardButton(text='نمایش مشخصات شما', callback_data=user_information),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        text=f'سلام آقای {user_name}، به ربات خوش اومدی.',
        reply_markup=reply_markup
    )

async def user_information(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(text="مشخصات حساب کاربری شما:", reply_markup=InlineKeyboardMarkup())
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text='بروزرسانی', callback_data=user_information),
         InlineKeyboardButton(text='بازگشت', callback_data=start)
            ],
        [InlineKeyboardButton(text=f'نام حساب کاربری: {update.effective_user.first_name}', callback_data=start)]
    ])
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def bot_turnOn():
    bot = Bot(token=bot_token)
    async with bot:
        print(await bot.get_me())
    application = ApplicationBuilder().token(bot_token).build()
    application.add_handler(CommandHandler('start', start()))
    application.run_polling()

if __name__ == '__main__':
    asyncio.run(bot_turnOn())