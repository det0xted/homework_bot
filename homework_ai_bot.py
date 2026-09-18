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
1. Сфотографируй или отправь скриншот ДЗ
2. Напиши "Проверь мое ДЗ"
3. Я проверю и дам результат

Я автоматически проверю:
✅ Грамматику
✅ Орфографию
✅ Правильность ответов
✅ Логику

Начни! 📸
    """
    bot.reply_to(message, text)

@bot.message_handler(commands=['help'])
def help_command(message):
    text = """
📖 КАК ИСПОЛЬЗОВАТЬ:

1️⃣ Отправь фотку или скриншот ДЗ
2️⃣ Напиши "Проверь мое ДЗ" или просто отправь фото
3️⃣ Жди результат

⏳ Проверка займёт несколько секунд.

📊 Ты получишь отчет с:
- Количество ошибок
- Какие ошибки
- Оценка результата
- Рекомендации
    """
    bot.reply_to(message, text)

# ========== ОБРАБОТКА ФОТО И ДЗ ==========

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Обрабатывает фото с ДЗ"""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    # Сообщение статуса
    status_msg = bot.reply_to(message, "⏳ Анализирую фото...")
    
    try:
        # Загружаем фото
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохраняем локально
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        photo_path = f"{HOMEWORK_DIR}/{username}_{timestamp}.jpg"
        with open(photo_path, 'wb') as f:
            f.write(downloaded_file)
        
        # Конвертируем в base64
        with open(photo_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')
        
        # Отправляем в Claude для анализа
        analysis_result = analyze_homework_with_claude(image_data, message.caption or "")
        
        # Генерируем отчёты
        student_report = generate_student_report(analysis_result)
        teacher_report = generate_teacher_report(username, analysis_result)
        
        # Отправляем ученику (краткий отчёт)
        bot.edit_message_text(student_report, user_id, status_msg.message_id)
        
        # Отправляем учителю (подробный отчёт)
        if TEACHER_ID > 0:
            bot.send_message(TEACHER_ID, teacher_report)
        
    except Exception as e:
        error_msg = f"❌ Ошибка при обработке: {str(e)}"
        bot.edit_message_text(error_msg, user_id, status_msg.message_id)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработка текстовых сообщений"""
    user_id = message.from_user.id
    text = message.text.lower()
    
    if "проверь" in text or "check" in text:
        bot.reply_to(message, "📸 Отправь фото или скриншот ДЗ, которое хочешь проверить!")
    else:
        bot.reply_to(message, "👋 Отправь фото ДЗ или напиши /help")

# ========== АНАЛИЗ С CLAUDE (REST API) ==========

def analyze_homework_with_claude(image_base64, caption):
    """Анализирует фото ДЗ с помощью Claude Vision через REST API"""
    
    prompt = """
Ты проверяешь домашнее задание по английскому языку. Анализируй фото ДЗ и дай подробную проверку.

**Что проверять:**
1. Грамматические ошибки (времена, согласование, предлоги)
2. Орфографические ошибки (опечатки)
3. Правильность ответов на вопросы
4. Пунктуация
5. Логичность и полнота ответов

**Формат ответа (ВАЖНО - ЖЁСТКИЙ ФОРМАТ):**

```
ERRORS_COUNT: [количество ошибок]
GRADE: [оценка от 1-10]
PERCENTAGE: [процент правильности]

ERRORS:
[ошибка 1]
[ошибка 2]
[ошибка 3]
...

SUMMARY: [краткое резюме - 1-2 предложения]

RECOMMENDATIONS:
[рекомендация 1]
[рекомендация 2]
...
```

**ВАЖНО:**
- Будь объективен
- Находи реальные ошибки, не мелочись
- Если ошибок нет - напиши ERRORS_COUNT: 0
- Пиши на русском и английском где нужно
"""

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "content-type": "application/json"
    }

    body = {
        "model": "claude-opus-4-1",
        "max_tokens": 1500,
        "messages": [
            {
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
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
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
        return result['content'][0]['text']
    except Exception as e:
        return f"Ошибка при анализе: {str(e)}"

def parse_claude_response(response_text):
    """Парсит ответ Claude в структурированный формат"""
    result = {
        "errors_count": 0,
        "grade": 0,
        "percentage": 0,
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

# ========== ГЕНЕРАЦИЯ ОТЧЁТОВ ==========

def generate_student_report(claude_response):
    """Краткий отчёт для ученика"""
    result = parse_claude_response(claude_response)
    
    # Эмодзи в зависимости от оценки
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
