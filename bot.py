import logging
import sys
import time
from uuid import uuid4

import telebot
from telebot import types

import texts
from api.cse import CSEAPIError, GoogleSearchEngine, SearchResult
from ext import parse_query

TG_API_TOKEN = "<YOUR_TELEGRAM_API_TOKEN>"
GOOGLE_API_KEY = "<YOUR_GOOGLE_API_KEY>"
SEARCH_ENGINE_ID = "<YOUR_SEARCH_ENGINE_ID>"

bot = telebot.TeleBot(TG_API_TOKEN)
cse = GoogleSearchEngine(GOOGLE_API_KEY, SEARCH_ENGINE_ID)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger()


# start command
@bot.message_handler(commands=['start'])
def start_message(message: types.Message) -> None:
    """Handle `/start` command."""
    first_name = message.from_user.first_name
    chat_id = message.from_user.id
    bot.send_message(
        chat_id,
        texts.START_MSG.format(first_name=first_name, chat_id=chat_id),
        parse_mode="Markdown"
    )


# help command
@bot.message_handler(commands=['help'])
def help_message(message: types.Message) -> None:
    """Handle `/help` command."""
    chat_id = message.from_user.id
    message_id = message.message_id
    kb = [
        [
            types.InlineKeyboardButton(
                "Search now 🔎",
                switch_inline_query_current_chat=" "
            )
        ]
    ]
    bot.send_message(
        chat_id,
        texts.HELP_MSG,
        parse_mode="Markdown",
        reply_to_message_id=message_id,
        reply_markup=types.InlineKeyboardMarkup(kb)
    )


# handle inline queries
@bot.inline_handler(func=lambda query: len(query.query) > 0)
def inline_query_handler(inline_query: types.InlineQuery) -> None:
    """Handle every inline query that is not empty."""
    parsed_query = parse_query(inline_query.query)
    # query string without commands
    query_text = parsed_query.query
    query_id = str(inline_query.id)
    results = []
    not_found = types.InlineQueryResultArticle(
        id=str(uuid4()),
        title="⚠️ No results found",
        description=texts.NOT_FOUND_MSG,
        input_message_content=types.InputTextMessageContent(
            message_text="not_found_result"
        )
    )
    page = 1
    # handle query commands
    if parsed_query.commands:
        for command in parsed_query.commands:
            if command.name.lower() == "page":
                try:
                    value = abs(int(command.value))
                    page = value if value > 1 else 1
                except ValueError:
                    continue
    try:
        search_result: SearchResult = cse.search(
            query_text, page, only_image=True)
    except CSEAPIError as e:
        logger.error(f"Error while searching for {query_text!r}: {e}")
        bot.answer_inline_query(query_id, [])
    else:
        # for every item in search result that has image attribute, add it to results
        if search_result.items:
            for item in search_result.items:
                if item.image:
                    results.append(
                        types.InlineQueryResultPhoto(
                            id=str(uuid4()),
                            photo_url=item.link,
                            thumb_url=item.image.thumbnailLink,
                            photo_width=item.image.width,
                            photo_height=item.image.height,
                            title=item.title
                        )
                    )
    if not results:
        bot.answer_inline_query(query_id, [not_found])
    else:
        bot.answer_inline_query(query_id, results, cache_time=60)


# message handler
@bot.message_handler(func=lambda message: True)
def message_handler(message: types.Message) -> None:
    """Handle every message that is not a command."""
    text = message.text
    chat_id = message.chat.id
    message_id = message.message_id
    if text == "not_found_result":
        bot.delete_message(chat_id, message_id)
    else:
        bot.send_message(chat_id, texts.NOT_FOUND_MSG)


def start_polling() -> None:
    """Start polling and responding to every message."""
    logger.info("Bot polling started...")
    bot.infinity_polling()
    while True:
        time.sleep(2)


if __name__ == '__main__':
    try:
        start_polling()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
        cse.close()
        sys.exit()
