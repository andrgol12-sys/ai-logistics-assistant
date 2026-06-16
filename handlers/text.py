"""
Text Message Handler.
Handles regular text messages from users using pyTelegramBotAPI.
"""

from telebot import types
from telebot.util import extract_arguments
from bot import bot
from services.router import route_text_request
from utils.logging import logger
from utils.helpers import user_sessions
from config import BotMode


VALID_MODES = [BotMode.TEXT, BotMode.VOICE, BotMode.VISION, BotMode.RAG]

MODE_DESCRIPTIONS = {
    BotMode.TEXT: "📝 Текстовый режим - обычный диалог с GPT-4o",
    BotMode.VOICE: "🎤 Голосовой режим - ответы будут приходить голосом",
    BotMode.VISION: "📸 Режим Vision - отправляйте изображения для анализа",
    BotMode.RAG: "📚 Режим RAG - работа с базой знаний",
}


def is_plain_text_message(message: types.Message) -> bool:
    """Match user text messages, excluding commands."""
    if getattr(message, "content_type", None) != "text":
        return False
    text = getattr(message, "text", None)
    if not text:
        return False
    return not text.lstrip().startswith("/")


@bot.message_handler(commands=["mode"])
async def cmd_mode(message: types.Message):
    """Handle /mode command - change bot mode."""
    user_id = message.from_user.id
    logger.info(f"User {user_id} invoked /mode: {message.text!r}")

    try:
        mode_arg = extract_arguments(message.text or "")
        if mode_arg is not None:
            mode_arg = mode_arg.strip()

        if not mode_arg:
            current_mode = user_sessions.get_mode(user_id)
            mode_info = (
                f"🔧 Текущий режим: {current_mode}\n\n"
                "Доступные режимы:\n"
                "• text - текстовый режим (GPT-4o)\n"
                "• voice - голосовой режим\n"
                "• vision - анализ изображений\n"
                "• rag - база знаний\n\n"
                "Использование:\n"
                "/mode text\n"
                "/mode rag"
            )
            await bot.send_message(message.chat.id, mode_info, parse_mode="")
            return

        new_mode = mode_arg.split()[0].lower()
        if new_mode not in VALID_MODES:
            await bot.send_message(
                message.chat.id,
                f"❌ Неизвестный режим: {new_mode}\n\n"
                f"Доступные режимы: {', '.join(VALID_MODES)}",
                parse_mode="",
            )
            return

        user_sessions.set_mode(user_id, new_mode)
        logger.info(f"User {user_id} switched to mode: {new_mode}")

        await bot.send_message(
            message.chat.id,
            f"✅ Режим изменён: {new_mode}\n\n{MODE_DESCRIPTIONS[new_mode]}",
            parse_mode="",
        )
    except Exception as e:
        logger.error(f"Error in /mode command for user {user_id}: {e}", exc_info=True)
        await bot.send_message(
            message.chat.id,
            "❌ Не удалось сменить режим. Попробуйте ещё раз: /mode rag",
            parse_mode="",
        )


@bot.message_handler(commands=['image'])
async def cmd_image(message: types.Message):
    """Handle /image command - generate image with specific parameters."""
    user_id = message.from_user.id
    
    # Parse command arguments
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        help_text = """🎨 **Генерация изображений**

**Автоматическая генерация:**
Просто напишите "Нарисуй...", "Создай изображение..." и ИИ автоматически создаст картинку.

**Примеры:**
• Нарисуй кота в космосе
• Создай изображение футуристического города
• Сгенерируй картинку заката на море

**Прямая команда:**
/image <описание>

Бот использует DALL-E 3 для создания изображений высокого качества."""
        
        await bot.send_message(message.chat.id, help_text)
        return
    
    prompt = args[1]
    
    logger.info(f"Direct image generation request from user {user_id}")
    
    # Show typing indicator
    await bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Generate image directly
        from services.router import route_image_generation_request
        from utils.helpers import cleanup_file
        
        response = await route_image_generation_request(
            user_id=user_id,
            prompt=prompt,
            original_text=prompt
        )
        
        # Send text response
        await bot.send_message(message.chat.id, response["text"], parse_mode="")
        
        # Send image if generated successfully
        if response.get('has_image') and response.get('image_path'):
            await bot.send_chat_action(message.chat.id, 'upload_photo')
            
            image_path = response['image_path']
            try:
                with open(image_path, 'rb') as photo:
                    caption = response.get('revised_prompt', '')
                    if len(caption) > 1024:
                        caption = caption[:1021] + "..."
                    
                    await bot.send_photo(
                        message.chat.id,
                        photo,
                        caption=caption if caption else None
                    )
            finally:
                cleanup_file(image_path)
    
    except Exception as e:
        logger.error(f"Error in /image command: {e}", exc_info=True)
        await bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при генерации изображения.\n"
            "Попробуйте еще раз или перефразируйте запрос.",
            parse_mode="",
        )


@bot.message_handler(func=is_plain_text_message)
async def handle_text_message(message: types.Message):
    """Handle regular text messages."""
    user_id = message.from_user.id
    text = message.text.strip()
    mode = user_sessions.get_mode(user_id)

    logger.info(
        f"Text message from user {user_id} (mode={mode}): {text[:80]}"
        f"{'...' if len(text) > 80 else ''}"
    )
    
    # Show typing indicator
    await bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Route request
        response = await route_text_request(user_id, text)
        
        # Check if response contains an image
        if response.get('has_image') and response.get('image_path'):
            # Send text response first
            await bot.send_message(message.chat.id, response["text"], parse_mode="")
            
            # Then send the generated image
            from utils.helpers import cleanup_file
            image_path = response['image_path']
            
            try:
                # Show uploading photo action
                await bot.send_chat_action(message.chat.id, 'upload_photo')
                
                # Send image
                with open(image_path, 'rb') as photo:
                    caption = response.get('revised_prompt', '')
                    if len(caption) > 1024:
                        caption = caption[:1021] + "..."
                    
                    await bot.send_photo(
                        message.chat.id, 
                        photo,
                        caption=caption if caption else None
                    )
                
                logger.info(f"Image sent to user {user_id}")
                
            finally:
                # Cleanup generated image file
                cleanup_file(image_path)
            
            return
        
        if mode == BotMode.VOICE:
            # Generate voice response
            from services.tts import generate_voice_response
            from utils.helpers import cleanup_file
            
            voice_path = await generate_voice_response(
                response["text"],
                voice=user_sessions.get_voice(user_id)
            )
            
            try:
                # Send text first
                await bot.send_message(message.chat.id, response["text"], parse_mode="")
                
                # Then send voice
                with open(voice_path, 'rb') as audio:
                    await bot.send_voice(message.chat.id, audio)
                
            finally:
                # Cleanup
                cleanup_file(voice_path)
        else:
            await bot.send_message(message.chat.id, response["text"], parse_mode="")
            logger.info(f"Text response sent to user {user_id} (mode={mode})")
    
    except Exception as e:
        logger.error(f"Error handling text message: {e}", exc_info=True)
        await bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при обработке сообщения.\n"
            "Попробуйте еще раз или используйте /reset для сброса.",
            parse_mode="",
        )
