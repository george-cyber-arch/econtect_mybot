import os
import json
import random
from telegram.constants import ChatAction
from telegram import InputMediaPhoto
import asyncio
from utils_id import get_next_answer_id
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from utils import load_data, save_data
from dotenv import load_dotenv
load_dotenv()

ADMIN_ID = "924475051"
USERS_FILE = "data/users.json"
ANSWERS_FILE = "data/answers.json"
VOTES_FILE = "data/votes.json"
SEEN_FILE = "data/seen.json"
CONFIG_FILE = "data/config.json"
config = load_data(CONFIG_FILE)
MAX_CHARS = config.get("max_chars", 20)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_data(USERS_FILE)
    user_id = str(user.id)

    # 👀 Перевіряємо чи є реферальне посилання
    args = context.args
    referred_by = args[0] if args else None
    is_new_user = user_id not in users

    if is_new_user:
        users[user_id] = {
            "username": user.username or user.first_name,
            "answers_left": 1,
            "points": 0,
            "invited_users": [],
            "bonus_points": 0.0
        }

        # 🎁 Якщо користувач був запрошений
        if referred_by and referred_by != user_id and referred_by in users:
            inviter = users[referred_by]
            inviter.setdefault("invited_users", [])
            inviter.setdefault("bonus_points", 0.0)

            if user_id not in inviter["invited_users"]:
                inviter["invited_users"].append(user_id)

                # Додаємо 0.5, але не більше 5
                if inviter["bonus_points"] < 5.0:
                    inviter["bonus_points"] += 0.5
                    inviter["bonus_points"] = min(inviter["bonus_points"], 5.0)

                    await context.bot.send_message(
                        chat_id=int(referred_by),
                        text=f"🎉 Хтось приєднався за твоїм посиланням! Ти отримав +0.5 бонусного бала (разом: {inviter['bonus_points']} / 5)"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=int(referred_by),
                        text=f"ℹ️ Хтось приєднався за твоїм посиланням, але ти вже досягнув ліміту бонусів (5 балів)."
                    )
    else:
        users[user_id]["username"] = user.username or user.first_name
        users[user_id].setdefault("answers_left", 1)
        users[user_id].setdefault("points", 0)
        users[user_id].setdefault("invited_users", [])
        users[user_id].setdefault("bonus_points", 0.0)

    # ✅ Save після усіх змін
    save_data(USERS_FILE, users)

    # 📨 Надсилаємо вітальне повідомлення
    config = load_data(CONFIG_FILE)
    question = config.get("question", "Питання наразі не встановлено.")
    max_chars = config.get("max_chars", 20)

    await update.message.reply_text(
        f"👋 Вітаємо!\n"
        f"🟡 Твоє завдання:\n\n"
        f"{question}\n\n"
        f"✏️ /feed – щоб переглянути коментарі інших\n"
    )

    welcome_photo_id = config.get("welcome_photo_id")
    if welcome_photo_id:
        await context.bot.send_chat_action(chat_id=user.id, action=ChatAction.UPLOAD_PHOTO)
        await context.bot.send_photo(chat_id=user.id, photo=welcome_photo_id)







async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_data(USERS_FILE)
    user_id = str(user.id)

    # Auto-register user if not yet in users.json
    if user_id not in users:
        users[user_id] = {
            "username": user.username or user.first_name,
            "answers_left": 1,
            "points": 0,
            "invited_users": [],
            "bonus_given": False
        }
    
    save_data(USERS_FILE, users)
    user_data = users[user_id]

    if user_data["answers_left"] <= 0:
        answers = load_data(ANSWERS_FILE)
        has_answer = any(str(a["user_id"]) == user_id for a in answers.values())

        if not has_answer:
            print(f"🛠 Resetting 'answers_left' for {user_id} because no answer found")
            user_data["answers_left"] = 1
            save_data(USERS_FILE, users)
        else:
            await update.message.reply_text("❗️ Ви вже відповіли.\n\n/delete, щоб видалити відповіді і надіслати нову.\n\n/feed – подивитися коментарі інших.")
            return

    message_text = update.message.text.strip()

    config = load_data(CONFIG_FILE)
    max_chars = config.get("max_chars", 20)
    if len(message_text) > max_chars:
        await update.message.reply_text(f"Ваша відповідь занадто довга. Максимум {max_chars} символів.")
        return

    answers = load_data(ANSWERS_FILE)

    answer_id = get_next_answer_id()


    answers[answer_id] = {
        "user_id": user.id,
        "username": user.username or user.first_name,
        "text": message_text,
        "score": 0
    }

    save_data(ANSWERS_FILE, answers)
    users[user_id]["answers_left"] -= 1
    save_data(USERS_FILE, users)


    total_comments = len(answers)

    config = load_data(CONFIG_FILE)
    last_notify = config.get("last_notify_count", 0)

    if total_comments // 10 > last_notify // 10:
        config["last_notify_count"] = total_comments
        save_data(CONFIG_FILE, config)

        message = f"🎉 У стрічці вже {total_comments} коментарів! Голосуй, щоб бути видимим для інших - /feed!"
        for uid in users:
            try:
                await context.bot.send_message(chat_id=int(uid), text=message)
            except Exception as e:
                print(f"❌ Не вдалося надіслати повідомлення користувачу {uid}: {e}")

    print(f"✅ Answer saved from {user.username or user.first_name}: {message_text}")
    await update.message.reply_text(
        "Вау, ти такий креативний! 😮‍💨 Тепер запроси друга, щоб бути максимально видимим для інших! /myinvite\n\n/feed – подивитися коментарі інших\n\n/points – мої бали\n/top – лідери\n/delete - замінити відповідь/i."
    )







async def feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_data(USERS_FILE)
    answers = load_data(ANSWERS_FILE)
    seen = load_data(SEEN_FILE)

    if user_id not in users:
        await update.message.reply_text("Натисніть /start спочатку.")
        return

    # 🔄 Переконайся, що всі seen ID — це рядки
    seen_ids = set(str(aid) for aid in seen.get(user_id, []))

    # 🔍 Вибір тільки відповідей, які ще не були переглянуті
    unseen = [
        (aid, a) for aid, a in answers.items()
        if str(aid) not in seen_ids and a["user_id"] != int(user_id)
    ]

    # 🐞 DEBUG INFO
    print(f"🔍 User ID: {user_id}")
    print(f"👁️ Seen answer IDs: {seen_ids}")
    print(f"📦 All answer IDs: {list(answers.keys())}")
    print(f"🆕 Unseen answer IDs: {[aid for aid, _ in unseen]}")
    for aid, a in answers.items():
        print(f"➡️ Answer {aid}: by user {a['user_id']}, text: {a['text']}")

    if not unseen:
        await update.message.reply_text("👻 Ви переглянули всі відповіді.\n\n/myinvite, щоб запросити друзів і отримати бали до рейтингу /top 💰")
        return

    # 🎯 Випадкова невидима відповідь
    aid, answer = random.choice(unseen)

    # ✅ Позначити як переглянуту
    seen.setdefault(user_id, []).append(str(aid))
    save_data(SEEN_FILE, seen)

    text = f"❓ {answer['text']}"

    buttons = [
        [InlineKeyboardButton("😂", callback_data=f"vote|{aid}|1")],
        [InlineKeyboardButton("😃", callback_data=f"vote|{aid}|2")],
        [InlineKeyboardButton("💀", callback_data=f"vote|{aid}|-1")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))






async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    votes = load_data(VOTES_FILE)
    answers = load_data(ANSWERS_FILE)
    users = load_data(USERS_FILE)

    _, aid, value = query.data.split("|")
    vote_key = f"{user_id}_{aid}"

    if vote_key in votes:
        await query.edit_message_text("⛔ Ви вже голосували за цю відповідь.")
        return

    value = int(value)
    votes[vote_key] = value

    answer = answers.get(aid)
    if not answer:
        await query.edit_message_text("⚠️ Відповідь не знайдено.")
        return

    answer_user_id = str(answer["user_id"])
    answer["score"] = answer.get("score", 0)

    # Ініціалізуємо лічильники
    answer["positive_reactions"] = answer.get("positive_reactions", 0)
    answer["negative_reactions"] = answer.get("negative_reactions", 0)

    # Отримуємо бонус користувача (0.0, якщо не існує)
    bonus = users.get(answer_user_id, {}).get("bonus_points", 0.0)

    # 👍 Голос 1 (10 балів + бонус, якщо є)
    if value == 1:
        answer["score"] += 10
        answer["positive_reactions"] += 1
        if bonus > 0:
            answer["score"] += bonus

    # ✌️ Голос 2 (2 бали + бонус, якщо є)
    elif value == 2:
        answer["score"] += 2
        answer["positive_reactions"] += 1
        if bonus > 0:
            answer["score"] += bonus

    # 👎 Голос 3 (–3 бали, без бонусу)
    else:
        answer["score"] -= 3
        answer["negative_reactions"] += 1

    save_data(VOTES_FILE, votes)
    save_data(ANSWERS_FILE, answers)

    await query.edit_message_text("✅ Твій голос зараховано.")

    # ⚠️ Симулюємо /feed
    class FakeMessage:
        def __init__(self, user_id):
            self.from_user = type("User", (), {"id": int(user_id)})
            self.effective_user = self.from_user

        async def reply_text(self, text, reply_markup=None):
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)

    fake_update = Update(update.update_id, message=FakeMessage(user_id))
    await feed(fake_update, context)







async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_data(USERS_FILE)
    answers = load_data(ANSWERS_FILE)
    config = load_data(CONFIG_FILE)

    current_user_id = str(update.effective_user.id)
    reveal_names = config.get("reveal_names", False)
    hide_comments = config.get("hide_comments", False)

    leaderboard_entries = []

    for aid, answer in answers.items():
        uid = str(answer["user_id"])
        user = users.get(uid)
        if not user:
            continue

        username = user.get("username") or f"Anon_{uid[-4:]}"
        display_name = f"@{username}" if reveal_names and user.get("username") else f"Anon_{uid[-4:]}"
        
        # ✅ Використовуємо тільки score (бонус вже враховано під час голосування)
        total_score = answer.get("score", 0)

        leaderboard_entries.append({
            "user_id": uid,
            "username": display_name,
            "text": "" if hide_comments else answer.get("text", ""),
            "points": round(total_score, 1)
        })

    leaderboard_entries.sort(key=lambda x: x["points"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]

    message = "🏆 Топ-відповіді:\n\n"
    for i, entry in enumerate(leaderboard_entries[:10], start=1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        message += f"{medal} {entry['username']} – {entry['points']} балів\n"
        if entry['text']:
            message += f"📝 {entry['text']}\n"
        message += "\n"

    # Якщо твоя відповідь не в топі – покажи її
    if current_user_id not in [e["user_id"] for e in leaderboard_entries[:10]]:
        for i, entry in enumerate(leaderboard_entries, start=1):
            if entry["user_id"] == current_user_id:
                message += f"👤 ВИ ({i} місце): {entry['username']}\n"
                message += f"🏅 {entry['points']} балів\n"
                if entry['text']:
                    message += f"📝 {entry['text']}\n"
                break

    await update.message.reply_text(message)


















#DELETE ANSWER
async def delete_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_data(USERS_FILE)
    answers = load_data(ANSWERS_FILE)
    votes = load_data(VOTES_FILE)

    deleted = False
    to_delete = []

    # Find answers to delete
    for aid, answer in answers.items():
        if str(answer.get("user_id")) == user_id:
            to_delete.append(aid)

    # Delete answers and related votes
    for aid in to_delete:
        del answers[aid]
        deleted = True

        # Delete all votes related to that answer
        vote_keys_to_remove = [k for k in votes if k.endswith(f"_{aid}")]
        for vk in vote_keys_to_remove:
            del votes[vk]

    if deleted:
        users[user_id]["answers_left"] = 1
        users[user_id]["points"] = 0
        save_data(ANSWERS_FILE, answers)
        save_data(USERS_FILE, users)
        save_data(VOTES_FILE, votes)
        await update.message.reply_text("🗑️ Вашу відповідь (відповіді) видалено. Тепер ви можете надіслати нову.")
    else:
        await update.message.reply_text("У вас немає відповіді для видалення.")




async def toggle_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # Optional: restrict to your admin user ID
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Це доступно лише адміну.")
        return

    config = load_data(CONFIG_FILE)
    reveal = config.get("reveal_names", False)
    config["reveal_names"] = not reveal
    save_data(CONFIG_FILE, config)

    status = "імена тепер видно" if config["reveal_names"] else "імена приховано"
    await update.message.reply_text(f"✅ Готово: {status}.")



async def toggle_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Це доступно лише адміну.")
        return

    config = load_data(CONFIG_FILE)
    hide = config.get("hide_comments", False)
    config["hide_comments"] = not hide
    save_data(CONFIG_FILE, config)

    status = "коментарі тепер видно" if not config["hide_comments"] else "коментарі приховано"
    await update.message.reply_text(f"✅ Готово: {status}.")




async def check_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_data(USERS_FILE)
    answers = load_data(ANSWERS_FILE)

    if user_id not in users:
        await update.message.reply_text("⛔ Ви ще не зареєстровані. Напишіть /start.")
        return

    user_answers = [a for a in answers.values() if str(a["user_id"]) == user_id]
    if not user_answers:
        await update.message.reply_text("У вас ще немає відповідей.")
        return

    bonus_used = users[user_id].get("bonus_points", 0.0)

    message = "💰 Твої відповіді та бали:\n\n"
    user_best_score = 0
    for a in user_answers:
        text = a.get("text", "").strip() or "(без тексту)"
        score = a.get("score", 0)
        user_best_score = max(user_best_score, score)
        message += f"– {text} — {score} балів\n"

    # Знаходимо місце в загальному рейтингу за найкращим коментарем
    all_scores = [(str(a["user_id"]), a.get("score", 0)) for a in answers.values()]
    all_scores.sort(key=lambda x: x[1], reverse=True)

    rank = [uid for uid, _ in all_scores].index(user_id) + 1

    message += f"\n🎁 Реферальний бонус: ({bonus_used}/5 бонусів)"
    message += f"\n📊 Ти зараз {rank} у рейтингу! /top"
    message += "\n\n/myinvite — запроси друга й отримай ще бонуси!"
    message += "\n/donate — додай ще відповіді за донат!"

    await update.message.reply_text(message)










#donate
async def donate_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "💸 *Збільш шанси на перемогу!*\n\n"
        "Додай ще ТРИ коментарі у стрічку — просто задонать на *Монобанку* (донат від 50 грн.) і надішли квитанцію мені – [@SireXl](https://t.me/SireXl).\n\n"
        "🔗 [Задонатити на банку](https://send.monobank.ua/jar/mvaEKosuB)\n\n"
        "Разом з квитанцією обов’язково вкажи свій *ID* (перевірити можна тут: @userinfobot).\n\n"
        "_Бали за кожен коментар сумуються окремо._\n\n"
        "*(частину коштів ми спрямуємо на благодійність /info)*"
    )
    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)






#Message
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Ця команда доступна лише адміну.")
        return

    users = load_data(USERS_FILE)

    # Case 1: Admin is replying to a photo
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        caption = " ".join(context.args) if context.args else ""
        photo = update.message.reply_to_message.photo[-1].file_id
        count = 0
        for uid in users:
            try:
                await context.bot.send_photo(chat_id=int(uid), photo=photo, caption=caption)
                count += 1
            except Exception as e:
                print(f"❌ Не вдалося надіслати фото до {uid}: {e}")
        await update.message.reply_text(f"📸 Фото з підписом надіслано {count} користувачам.")
        return

    # Case 2: Regular text message
    if not context.args:
        await update.message.reply_text("❗ Напишіть повідомлення після /m або відповідайте на фото.")
        return

    text = " ".join(context.args)
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=text)
            count += 1
        except Exception as e:
            print(f"❌ Не вдалося надіслати {uid}: {e}")

    await update.message.reply_text(f"📢 Текст надіслано {count} користувачам.")
    # Case 3: Admin is replying to a poll
    if update.message.reply_to_message and update.message.reply_to_message.poll:
        poll = update.message.reply_to_message.poll
        question = poll.question
        options = [opt.text for opt in poll.options]
        allows_multiple_answers = poll.allows_multiple_answers
        is_anonymous = poll.is_anonymous

        count = 0
        for uid in users:
            try:
                await context.bot.send_poll(
                    chat_id=int(uid),
                    question=question,
                    options=options,
                    is_anonymous=is_anonymous,
                    allows_multiple_answers=allows_multiple_answers
                )
                count += 1
            except Exception as e:
                print(f"❌ Не вдалося надіслати опитування до {uid}: {e}")

        await update.message.reply_text(f"📊 Опитування надіслано {count} користувачам.")
        return




admin_albums = {}  # media_group_id -> list of photo file_ids
admin_album_captions = {}  # media_group_id -> caption
pending_group_id = None  # останній альбом

# Крок 1: приймаємо альбом, але НЕ надсилаємо
async def handle_admin_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pending_group_id

    message = update.message
    user_id = str(update.effective_user.id)
    if str(user_id) != ADMIN_ID:
        return

    if not message.media_group_id or not message.photo:
        return

    group_id = message.media_group_id
    photo_file_id = message.photo[-1].file_id

    if group_id not in admin_albums:
        admin_albums[group_id] = []

    admin_albums[group_id].append(photo_file_id)
    pending_group_id = group_id

    # Повідомлення для адміна
    await message.reply_text("📸 Фото додано до альбому. Коли все готово, напиши /sendalbum ПІДПИС")

# Крок 2: надсилаємо альбом вручну
async def send_admin_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pending_group_id

    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Лише для адміна.")
        return

    if not pending_group_id or pending_group_id not in admin_albums:
        await update.message.reply_text("❗ Немає збереженого альбому. Спочатку надішліть альбом.")
        return

    caption = " ".join(context.args) if context.args else ""
    photos = admin_albums.pop(pending_group_id)
    pending_group_id = None

    media_group = []
    for i, pid in enumerate(photos):
        if i == 0:
            media_group.append(InputMediaPhoto(media=pid, caption=caption, parse_mode="HTML"))
        else:
            media_group.append(InputMediaPhoto(media=pid))

    users = load_data(USERS_FILE)
    sent = 0
    for uid in users:
        try:
            await context.bot.send_media_group(chat_id=int(uid), media=media_group)
            sent += 1
        except Exception as e:
            print(f"❌ Не вдалося до {uid}: {e}")

    await update.message.reply_text(f"✅ Альбом із {len(photos)} фото надіслано {sent} користувачам.")








#clear
async def clear_all_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Ця команда лише для адміну.")
        return

    # Clear answers, votes, seen
    save_data(ANSWERS_FILE, {})
    save_data(VOTES_FILE, {})
    save_data(SEEN_FILE, {})

    # Reset all user points and answers_left
    users = load_data(USERS_FILE)
    for u in users.values():
        u["points"] = 0
        u["answers_left"] = 1
    save_data(USERS_FILE, users)

    await update.message.reply_text("🧹 Всі відповіді, голоси та очки очищено.")




#stephoto
# /setphoto – адмін відповідає на фото, яке стане привітальним
async def set_welcome_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Лише для адміністратора.")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("📸 Відповідай на повідомлення з фото, щоб встановити його.")
        return

    photo_id = update.message.reply_to_message.photo[-1].file_id
    config = load_data(CONFIG_FILE)
    config["welcome_photo_id"] = photo_id
    save_data(CONFIG_FILE, config)

    await update.message.reply_text("✅ Фото встановлено. Воно буде показане після /start.")



#deletephoto
async def delete_welcome_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Лише для адміністратора.")
        return

    config = load_data(CONFIG_FILE)

    if "welcome_photo_id" in config:
        del config["welcome_photo_id"]
        save_data(CONFIG_FILE, config)
        await update.message.reply_text("🗑️ Фото успішно видалено. Воно більше не буде показуватись після /start.")
    else:
        await update.message.reply_text("ℹ️ Жодне фото не встановлено.")


#set a new question
async def set_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Ця команда лише для адміністратора.")
        return

    if not context.args:
        await update.message.reply_text("❗ Після /question потрібно написати нове питання.")
        return

    new_question = " ".join(context.args).strip()
    config = load_data(CONFIG_FILE)
    config["question"] = new_question
    save_data(CONFIG_FILE, config)

    await update.message.reply_text(f"✅ Питання оновлено:\n\n🟡 {new_question}")


#max length of answer
async def set_maxlength(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Лише для адміністратора.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❗ Використання: /maxlength [число від 1 до 100]")
        return

    new_length = int(context.args[0])
    if not (1 <= new_length <= 500):
        await update.message.reply_text("❗ Максимальна довжина має бути від 1 до 500 символів.")
        return

    config = load_data(CONFIG_FILE)
    config["max_chars"] = new_length
    save_data(CONFIG_FILE, config)

    await update.message.reply_text(f"✅ Максимальна довжина відповіді встановлена: {new_length} символів.")


#grant command
async def grant_extra_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Лише для адміністратора.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❗ Використання: /grant [user_id або @username] [кількість]")
        return

    users = load_data(USERS_FILE)
    target = context.args[0]
    try:
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❗ Кількість має бути додатнім числом.")
        return

    # Find user by ID or @username
    target_id = None
    if target.startswith("@"):
        for uid, udata in users.items():
            if udata.get("username") and f"@{udata['username']}" == target:
                target_id = uid
                break
    elif target.isdigit():
        target_id = target if target in users else None

    if not target_id:
        await update.message.reply_text("❌ Користувача не знайдено.")
        return

    users[target_id]["answers_left"] = users[target_id].get("answers_left", 1) + amount
    save_data(USERS_FILE, users)

    await update.message.reply_text(
        f"✅ Користувачу {users[target_id].get('username', target_id)} надано {amount} додаткових відповідей."
    )




#Info
async def info_later(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_data(CONFIG_FILE)
    info_text = config.get("info_text", "ℹ️ Інформація про благодійність з’явиться пізніше.")
    await update.message.reply_text(info_text)



#Set info
async def set_info_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Ця команда лише для адміну.")
        return

    new_text = " ".join(context.args)
    if not new_text:
        await update.message.reply_text("❗ Введи новий текст після команди /setinfo.")
        return

    config = load_data(CONFIG_FILE)
    config["info_text"] = new_text
    save_data(CONFIG_FILE, config)

    await update.message.reply_text("✅ Текст для /info оновлено.")



#ALL FEED
async def view_all_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Ця команда лише для адміну.")
        return

    answers = load_data(ANSWERS_FILE)
    users = load_data(USERS_FILE)

    if not answers:
        await update.message.reply_text("⚠️ Відповідей ще немає.")
        return

    sorted_answers = sorted(answers.items(), key=lambda x: -x[1].get("score", 0))
    message = "📋 *Всі відповіді:*\n\n"

    for aid, a in sorted_answers:
        uid = str(a.get("user_id", ""))
        username = users.get(uid, {}).get("username", "NoUsername")
        text = a.get("text", "")
        score = a.get("score", 0)
        message += f"• `{uid}` ({username}): \"{text}\" — {score} балів\n"

    # If too long, send as multiple messages
    for chunk in split_message(message):
        await update.message.reply_text(chunk, parse_mode="Markdown")




def split_message(text, max_length=4000):
    lines = text.split("\n")
    chunks, chunk = [], ""
    for line in lines:
        if len(chunk) + len(line) + 1 > max_length:
            chunks.append(chunk)
            chunk = line + "\n"
        else:
            chunk += line + "\n"
    if chunk:
        chunks.append(chunk)
    return chunks


#Online
async def online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_data(USERS_FILE)
    count = len(users)
    await update.message.reply_text(f"👥 Кількість користувачів, які використовують бот: {count}")



# /invite command
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_data(USERS_FILE)
    answers = load_data(ANSWERS_FILE)

    if user_id not in users:
        await update.message.reply_text("⛔ Ви ще не зареєстровані. Напишіть /start.")
        return

    if not context.args:
        await update.message.reply_text("❗ Використання: /invite [user_id або @username]\n\nЗапросіть двох друзів і отримайте +50 бонусних балів! Ці бали будуть додані до всіх ваших поточних і наступних коментарів у межах конкурсу.")
        return

    invited = context.args[0]

    # Find invited user id
    invited_id = None
    if invited.startswith("@"):
        for uid, udata in users.items():
            if udata.get("username") and f"@{udata['username']}" == invited:
                invited_id = uid
                break
    elif invited.isdigit():
        invited_id = invited if invited in users else None

    if not invited_id:
        await update.message.reply_text("❌ Користувача не знайдено.")
        return

    if invited_id == user_id:
        await update.message.reply_text("❌ Не можна запросити себе.")
        return

    invited_users = users[user_id].setdefault("invited_users", [])

    if invited_id in invited_users:
        await update.message.reply_text("ℹ️ Цей користувач вже був запрошений.")
        return

    # Add to invited list
    invited_users.append(invited_id)

    # Check if user reached a multiple of 3 invites
    if len(invited_users) % 3 == 0:
        users[user_id]["bonus_points"] = users[user_id].get("bonus_points", 0) + 50

        # Add 50 bonus points to all user's answers
        for aid, answer in answers.items():
            if str(answer["user_id"]) == user_id:
                answer["score"] += 50

        save_data(ANSWERS_FILE, answers)
        await update.message.reply_text(f"🎉 Вітаємо! Ви запросили {len(invited_users)} користувачів і отримали +50 бонусних балів!")

    else:
        await update.message.reply_text(f"✅ Користувача додано в список запрошених. Усього запрошено: {len(invited_users)}.")

    save_data(USERS_FILE, users)



#ADD POINTS
async def add_bonus_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Ця команда лише для адміну.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("❗ Використання: /addpoints [user_id або @username] [кількість балів]")
        return

    target = context.args[0]
    try:
        points_to_add = int(context.args[1])  # can be negative
    except ValueError:
        await update.message.reply_text("❌ Кількість балів має бути числом.")
        return

    users = load_data(USERS_FILE)

    # 🔍 Find user by @username or ID
    target_id = None
    if target.startswith("@"):
        for uid, udata in users.items():
            if udata.get("username") and f"@{udata['username']}" == target:
                target_id = uid
                break
    elif target.isdigit():
        target_id = target if target in users else None

    if not target_id:
        await update.message.reply_text("❌ Користувача не знайдено.")
        return

    # ✅ Add or subtract points
    bonus_points[target_id] = bonus_points.get(target_id, 0) + points_to_add
    save_data("data/bonus_points.json", bonus_points)

    updated_total = bonus_points[target_id]
    await update.message.reply_text(
        f"✅ Користувачу {target} {'додано' if points_to_add >= 0 else 'знято'} {abs(points_to_add)} балів.\n"
        f"💰 Новий бонусний баланс: {updated_total}"
    )




#myinvite
async def my_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot_username = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start={user_id}"

    # Перше повідомлення — пояснення
    message1 = (
        "🎁 Це твоє реферальне посилання!\n"
        "Надішли його другу і отримай бонусні бали.\n"
        "Кожне запрошення додає +0.5 бала до усіх позитивних реакцій на твій коментар!"
    )

    # Друге повідомлення — саме посилання + call to action
    message2 = (
        f"🔗 {invite_link}\n\n"
        "Надішли найкреативніший коментар в чат і виграй 1000 грн! 💸\n\n"
        "Твоя мета — бути максимально оригінальним.\n"
        "Коментуй і оцінюй інших, щоб очолити таблицю лідерів 🏆\n\n"
        "(створено на благодійних засадах)"
    )

    await update.message.reply_text(message1)
    await update.message.reply_text(message2)










# Main function to set up the bot and handlers
def main():
    os.makedirs("data", exist_ok=True)
    for file, default in [
        (USERS_FILE, {}),
        (ANSWERS_FILE, {}),
        (VOTES_FILE, {}),
        (SEEN_FILE, {}),
        (CONFIG_FILE, {"question": "ЩО В СВІТІ НАЙДОВШЕ?"})
    ]:
        if not os.path.exists(file):
            with open(file, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)







    
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("feed", feed))
    app.add_handler(CommandHandler("top", leaderboard))
    app.add_handler(CommandHandler("delete", delete_answer))
    app.add_handler(CommandHandler("reveal", toggle_names))
    app.add_handler(CommandHandler("points", check_points))
    app.add_handler(CommandHandler("m", broadcast_message))
    app.add_handler(CommandHandler("clear", clear_all_data))
    app.add_handler(CommandHandler("setphoto", set_welcome_photo))
    app.add_handler(CommandHandler("deletephoto", delete_welcome_photo))
    app.add_handler(CommandHandler("question", set_question))
    app.add_handler(CommandHandler("maxlength", set_maxlength))
    app.add_handler(CommandHandler("grant", grant_extra_answer))
    app.add_handler(CommandHandler("donate", donate_info))
    app.add_handler(CommandHandler("info", info_later))
    app.add_handler(CommandHandler("setinfo", set_info_text))
    app.add_handler(CommandHandler("allfeed", view_all_feed))
    app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("addpoints", add_bonus_points))
    app.add_handler(CommandHandler("myinvite", my_invite))
    app.add_handler(CommandHandler('hide_comments', toggle_comments))
    app.add_handler(MessageHandler(filters.PHOTO, handle_admin_album))
    app.add_handler(CommandHandler("sendalbum", send_admin_album))















    app.add_handler(CallbackQueryHandler(handle_vote, pattern="^vote\\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот працює")
    app.run_polling()


if __name__ == "__main__":
    main()
