from telegram import Update
import logging
import requests
import bs4
import time
import asyncio
import tokens as tk
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Define states
WAITING_FOR_KEYWORD = 0

print("Bot starting!")
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"User {update.effective_user.id} started the bot.")
    await update.message.reply_text("Hello! I'm random image bot.")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    # Check if the user is in a conversation
    current_state = context.user_data.get("state")

    if current_state is not None and current_state == WAITING_FOR_KEYWORD:
        await update.message.reply_text("Please provide a keyword.")
    else:
        logger.info(f"Received message: {update.message.text}")
        await update.message.reply_text("Sorry, I don't think I understand this. Try command /image")


async def receive_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please provide a keyword:")
    context.user_data["state"] = WAITING_FOR_KEYWORD
    return WAITING_FOR_KEYWORD


async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyword = update.message.text
    logger.info(f"User {update.effective_user.id} used /image command with keyword '{keyword}'.")

    url = f'https://wallhaven.cc/search?q={keyword}&categories=100&purity=100&sorting=random&order=desc&ai_art_filter=1'
    count = 0
    try:
        r = requests.get(url)
        if r.status_code == 200:
            print("Successful")
            soup = bs4.BeautifulSoup(r.content, 'html.parser')
            images = soup.find_all('div', attrs={'class': 'thumbs-container thumb-listing infinite-scroll'})

            # Check if any images were found
            if not images or not any(image.find_all('ul') for image in images):
                await update.message.reply_text("No images found for the given keyword. Please try another keyword.")

                # Clear the state since no images found and get another keyword
                context.user_data.pop("state", None)
                return WAITING_FOR_KEYWORD

            else:
                for image in images:
                    my_image = image.find_all('ul')
                    if not my_image:
                        continue

                    my_image = my_image[0]
                    for i in my_image:
                        link = i.find('img', attrs={'class': 'lazyload'}).get("data-src") if i.find('img', attrs={
                            'class': 'lazyload'}) else None
                        if link:
                            image_link = 'https://w.wallhaven.cc/full/' + link[-10:-8] + '/wallhaven-' + link[-10:]
                            try:
                                img_req = requests.get(image_link)
                                if img_req.status_code == 200:
                                    private_chat_id = update.effective_chat.id
                                    message_text = await update.message.reply_text("Here's the image.")
                                    sent_image = await context.bot.send_photo(chat_id=private_chat_id,
                                                                              photo=image_link)

                                    """
                                        OPTIONAL
                                        Delete messages or image after 15 sec or any time you want.
                                    """
                                    asyncio.create_task(delete_message(context,
                                                                       private_chat_id,
                                                                       message_text.message_id,
                                                                       15))
                                    asyncio.create_task(delete_message(context,
                                                                       private_chat_id,
                                                                       sent_image.message_id,
                                                                       15))
                                    time.sleep(1)
                                    count += 1
                                    """
                                        Image limit, up to 3
                                    """
                                    if count == 3:
                                        break
                                else:
                                    time.sleep(0.5)
                                    continue
                            except requests.exceptions.RequestException as e:
                                await update.message.reply_text(f"Error occurred: {e}")
        else:
            await update.message.reply_text(f"Request failed! Status code: {r.status_code}")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Error occurred: {e}")
    except IndexError:
        await update.message.reply_text("No images found for the given keyword. Please try another keyword.")

    """
        Clear the state after send image or 
        you can keep getting images with different keywords:
    """
    context.user_data.pop("state", None)
    return ConversationHandler.END
    # return WAITING_FOR_KEYWORD

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    context.user_data.pop("state", None)
    return ConversationHandler.END


async def delete_message(context, chat_id, message_id, delay):
    await asyncio.sleep(delay)

    try:
        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=message_id)
        logger.info(f"Deleted message {message_id} in chat {chat_id}.")
    except Exception as e:
        logger.error(f"Failed to delete message {message_id} in chat {chat_id}: {e}")


def main() -> None:
    application = Application.builder().token(tk.token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('image', receive_keyword)],
        states={
            WAITING_FOR_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_image)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_command))
    application.run_polling()

if __name__ == "__main__":
    main()
