import telebot
import requests
import base64
import os
from datetime import datetime

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TEACHER_ID = int(os.getenv("TEACHER_ID", "0")) if os.getenv("TEACHER_ID") else 0
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "YOUR_CLAUDE_API_KEY_HERE")

bot = telebot.TeleBot(BOT_TOKEN)

# Папка для сохранения фото
HOMEWORK_DIR = "homework_submissions"
os.makedirs(HOMEWORK_DIR, exist_ok=True)

# ========== КОМАНДЫ ==========

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    text = f"""
👋 Привет, {username}!

Я твой помощник по проверке домашних заданий.

📸 **Как это работает:**
1️⃣ Вариант А: Отправь фото ДЗ + напиши "проверь мое дз"
2️⃣ Вариант Б: Напиши ДЗ текстом + напиши "проверь мое дз"
3️⃣ Жди результат!

Я проверю:
✅ Грамматику
✅ Орфографию
✅ Правильность ответов
✅ Логику

Начни! 📸 или ✍️
    """
    bot.reply_to(message, text)

@bot.message_handler(commands=['help'])
def help_command(message):
    text = """
📖 КАК ИСПОЛЬЗОВАТЬ:

**ВАРИАНТ 1 - Фото:**
1️⃣ Отправь фотку или скриншот ДЗ
2️⃣ Напиши "проверь мое дз"
3️⃣ Жди результат

**ВАРИАНТ 2 - Текст:**
1️⃣ Напиши ДЗ текстом (можешь в несколько сообщений)
2️⃣ В конце напиши "проверь мое дз"
3️⃣ Жди результат

⏳ Проверка займёт 20-30 секунд.

📊 Ты получишь отчет с:
- Количество ошибок
- Какие ошибки
- Оценка результата
- Рекомендации
    """
    bot.reply_to(message, text)

# ========== ОБРАБОТКА ФОТО ==========

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Обрабатывает фото с ДЗ"""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    # Сохраняем фото в памяти бота (в session)
    if not hasattr(bot, 'user_homework'):
        bot.user_homework = {}
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        photo_path = f"{HOMEWORK_DIR}/{username}_{timestamp}.jpg"
        with open(photo_path, 'wb') as f:
            f.write(downloaded_file)
        
        # Сохраняем путь к фото в памяти
        bot.user_homework[user_id] = {
            'type': 'photo',
            'path': photo_path,
            'username': username
        }
        
        bot.reply_to(message, "✅ Фото получено! Теперь напиши 'проверь мое дз'")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при загрузке фото: {str(e)}")

# ========== ОБРАБОТКА ТЕКСТА ==========

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработка текстовых сообщений"""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    text = message.text
    text_lower = text.lower()
    
    # Инициализируем память пользователя если нужно
    if not hasattr(bot, 'user_homework'):
        bot.user_homework = {}
    
    # Команда проверить
    if "проверь мое дз" in text_lower or "проверь дз" in text_lower or "check" in text_lower:
        
        # Вариант 1: есть сохранённое фото
        if user_id in bot.user_homework and bot.user_homework[user_id]['type'] == 'photo':
            homework_data = bot.user_homework[user_id]
            photo_path = homework_data['path']
            username = homework_data['username']
            
            status_msg = bot.reply_to(message, "⏳ Анализирую фото...")
            
            try:
                with open(photo_path, 'rb') as f:
                    image_data = base64.standard_b64encode(f.read()).decode('utf-8')
                
                analysis_result = analyze_homework_with_photo(image_data)
                
                student_report = generate_student_report(analysis_result)
                teacher_report = generate_teacher_report(username, analysis_result)
                
                bot.edit_message_text(student_report, user_id, status_msg.message_id)
                
                if TEACHER_ID > 0:
                    bot.send_message(TEACHER_ID, teacher_report)
                
                # Очищаем память
                del bot.user_homework[user_id]
                
            except Exception as e:
                error_msg = f"❌ Ошибка: {str(e)}"
                bot.edit_message_text(error_msg, user_id, status_msg.message_id)
        
        # Вариант 2: есть текст в этом же сообщении или в памяти
        else:
            # Достаём ДЗ из сообщения
            homework_text = text.replace("проверь мое дз", "").replace("проверь дз", "").replace("check", "").strip()
            
            if homework_text:
                status_msg = bot.reply_to(message, "⏳ Анализирую ДЗ...")
                
                try:
                    analysis_result = analyze_homework_with_text(homework_text)
                    
                    student_report = generate_student_report(analysis_result)
                    teacher_report = generate_teacher_report(username, analysis_result)
                    
                    bot.edit_message_text(student_report, user_id, status_msg.message_id)
                    
                    if TEACHER_ID > 0:
                        bot.send_message(TEACHER_ID, teacher_report)
                    
                    # Очищаем память если была
                    if user_id in bot.user_homework:
                        del bot.user_homework[user_id]
                    
                except Exception as e:
                    error_msg = f"❌ Ошибка: {str(e)}"
                    bot.edit_message_text(error_msg, user_id, status_msg.message_id)
            else:
                bot.reply_to(message, "❓ Не вижу ДЗ! Напиши ДЗ текстом или отправь фото, потом напиши 'проверь мое дз'")
    
    else:
        # Сохраняем текст если не команда
        if user_id not in bot.user_homework:
            bot.user_homework[user_id] = {
                'type': 'text',
                'content': text,
                'username': username
            }
            bot.reply_to(message, "✅ Текст получен! Напиши ещё ДЗ если нужно, потом 'проверь мое дз'")
        else:
            # Добавляем к существующему
            if bot.user_homework[user_id]['type'] == 'text':
                bot.user_homework[user_id]['content'] += "\n" + text
                bot.reply_to(message, "✅ Добавлено! Напиши 'проверь мое дз' когда готово")
            else:
                bot.reply_to(message, "ℹ️ У тебя уже есть фото! Напиши 'проверь мое дз' или отправь новое фото")

# ========== АНАЛИЗ С CLAUDE ==========

def analyze_homework_with_photo(image_base64):
    """Анализирует фото ДЗ"""
    
    prompt = """TASK: You are an English teacher checking A2-level student homework from a photo. You MUST find ALL grammar, spelling, and logic errors.

INSTRUCTIONS:
1. Read the homework text in the photo CAREFULLY
2. Find EVERY error - grammar, spelling, logic, punctuation
3. Do NOT miss any errors, no matter how small
4. Count total errors

TYPES OF ERRORS TO FIND:
1. Subject-verb agreement (he/she/it + verb, plural subjects + verb)
2. Wrong verb forms/tenses (present/past, do/does, is/are)
3. Missing articles (a/an/the)
4. Preposition errors (in/at/on, to/for, etc)
5. Spelling mistakes
6. Capitalization errors
7. Pluralization errors
8. Wrong word choice
9. Punctuation
10. Incomplete sentences

EXAMPLES OF ERRORS:
- "A crocodile is a dangerous animal. It live in swamps." → ERROR: "It live" should be "It lives"
- "Crocodiles is big" → ERROR: "is" should be "are"
- "Their very small" → ERROR: should be "They're" or "It's"
- "The mosquito bite people" → ERROR: should be "bites"

CRITICAL: Find EVERY error! Look carefully at the photo!

FORMAT (STRICT - DO NOT DEVIATE):

ERRORS_COUNT: [TOTAL NUMBER]
GRADE: [NUMBER 1-10]
PERCENTAGE: [PERCENTAGE 0-100]

ERRORS:
• [Error 1 - say what is wrong and what should be correct]
• [Error 2 - exact location and correction]
• [Error 3]

SUMMARY: [1-2 sentences about overall quality]

RECOMMENDATIONS:
• [Specific advice to improve]
• [Another tip]
"""

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "content-type": "application/json"
    }

    body = {
        "model": "claude-opus-4-1",
        "max_tokens": 1500,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_base64
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        print(f"DEBUG Photo: {result}")
        return result['content'][0]['text']
    except Exception as e:
        print(f"DEBUG Error: {str(e)}")
        return f"Ошибка: {str(e)}"

def analyze_homework_with_text(homework_text):
    """Анализирует текстовое ДЗ"""
    
    prompt = f"""TASK: You are an English teacher checking A2-level student homework. You MUST find ALL grammar, spelling, and logic errors.

HOMEWORK TO CHECK:
{homework_text}

TYPES OF ERRORS TO FIND:
1. Subject-verb agreement (he/she/it + verb, plural subjects + verb)
2. Wrong verb forms/tenses (present/past, do/does, is/are)
3. Missing articles (a/an/the)
4. Preposition errors (in/at/on, to/for, etc)
5. Spelling mistakes
6. Capitalization errors
7. Pluralization errors
8. Wrong word choice
9. Punctuation
10. Incomplete sentences

EXAMPLES OF ERRORS:
- "A crocodile is a dangerous animal. It live in swamps." → ERROR: "It live" should be "It lives"
- "Crocodiles is big" → ERROR: "is" should be "are"
- "Their very small" → ERROR: should be "They're" or "It's"
- "The mosquito bite people" → ERROR: should be "bites"

CRITICAL: Look for EVERY error, even small ones!

FORMAT (STRICT - DO NOT DEVIATE):

ERRORS_COUNT: [TOTAL NUMBER]
GRADE: [NUMBER 1-10]
PERCENTAGE: [PERCENTAGE 0-100]

ERRORS:
• [Error 1 - say what is wrong and what should be correct]
• [Error 2 - exact location and correction]
• [Error 3]

SUMMARY: [1-2 sentences about overall quality]

RECOMMENDATIONS:
• [Specific advice to improve]
• [Another tip]
"""

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "content-type": "application/json"
    }

    body = {
        "model": "claude-opus-4-1",
        "max_tokens": 1500,
        "messages": [{
            "role": "user",
            "content": prompt
        }]
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        print(f"DEBUG Text: {result}")
        return result['content'][0]['text']
    except Exception as e:
        print(f"DEBUG Error: {str(e)}")
        return f"Ошибка: {str(e)}"

def parse_claude_response(response_text):
    """Парсит ответ Claude"""
    result = {
        "errors_count": 0,
        "grade": 10,
        "percentage": 100,
        "errors": [],
        "summary": "",
        "recommendations": []
    }
    
    lines = response_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("ERRORS_COUNT:"):
            try:
                result["errors_count"] = int(line.split(':')[1].strip())
            except:
                pass
        
        elif line.startswith("GRADE:"):
            try:
                result["grade"] = int(line.split(':')[1].strip().split('/')[0])
            except:
                pass
        
        elif line.startswith("PERCENTAGE:"):
            try:
                result["percentage"] = int(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
        
        elif line.startswith("ERRORS:"):
            current_section = "errors"
        
        elif line.startswith("SUMMARY:"):
            current_section = "summary"
            summary_text = line.split(':', 1)[1].strip()
            result["summary"] = summary_text
        
        elif line.startswith("RECOMMENDATIONS:"):
            current_section = "recommendations"
        
        elif line and current_section == "errors" and not line.startswith('['):
            if line and line[0] in '•-*':
                result["errors"].append(line[1:].strip())
            else:
                result["errors"].append(line)
        
        elif line and current_section == "recommendations" and not line.startswith('['):
            if line and line[0] in '•-*':
                result["recommendations"].append(line[1:].strip())
            else:
                result["recommendations"].append(line)
    
    return result

# ========== ОТЧЁТЫ ==========

def generate_student_report(claude_response):
    """Краткий отчёт для ученика"""
    result = parse_claude_response(claude_response)
    
    if result["percentage"] == 100:
        emoji = "🌟"
        message = "ИДЕАЛЬНО!"
    elif result["percentage"] >= 80:
        emoji = "✅"
        message = "Хорошо!"
    elif result["percentage"] >= 60:
        emoji = "👍"
        message = "Неплохо, но есть ошибки"
    else:
        emoji = "⚠️"
        message = "Нужно исправить"
    
    report = f"""
{emoji} РЕЗУЛЬТАТЫ ПРОВЕРКИ

Ошибок: {result['errors_count']}
Оценка: {result['grade']}/10
Правильно: {result['percentage']}%

{message}

━━━━━━━━━━━━━━━━
Учитель получит подробный анализ.
    """
    
    return report

def generate_teacher_report(username, claude_response):
    """Подробный отчёт для учителя"""
    result = parse_claude_response(claude_response)
    
    report = f"""
📋 ОТЧЕТ ПО ДЗ
👤 От: @{username}
⏰ Время: {datetime.now().strftime("%Y-%m-%d %H:%M")}

━━━━━━━━━━━━━━━━
📊 СТАТИСТИКА:
Ошибок: {result['errors_count']}
Оценка: {result['grade']}/10
Правильно: {result['percentage']}%

━━━━━━━━━━━━━━━━
"""
    
    if result["errors"]:
        report += "❌ ОШИБКИ:\n"
        for i, error in enumerate(result["errors"][:10], 1):
            report += f"{i}. {error}\n"
        if len(result["errors"]) > 10:
            report += f"... и ещё {len(result['errors']) - 10} ошибок\n"
    
    if result["summary"]:
        report += f"\n📝 РЕЗЮМЕ:\n{result['summary']}\n"
    
    if result["recommendations"]:
        report += "\n💡 РЕКОМЕНДАЦИИ:\n"
        for rec in result["recommendations"][:5]:
            report += f"• {rec}\n"
    
    report += "\n━━━━━━━━━━━━━━━━\n"
    
    return report

# ========== ЗАПУСК ==========

if __name__ == "__main__":
    print("🤖 Умный бот проверки ДЗ запущен!")
    bot.infinity_polling(skip_pending=True, timeout=30)
