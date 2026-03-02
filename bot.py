import asyncio
import random
import logging
import requests
from urllib.parse import quote
from deep_translator import GoogleTranslator
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import os
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ ФИКС — очищаем переменные от пробелов/кавычек (Railway часто их добавляет)
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip('"').strip("'")
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения")

OMDB_BASE = "https://www.omdbapi.com"

IMDB_IDS = [
    "tt0111161","tt0068646","tt0071562","tt0468569","tt0050083",
    "tt0108052","tt0167260","tt0110912","tt0060196","tt0137523",
    "tt0120737","tt1375666","tt0109830","tt0133093","tt0080684",
    "tt0167261","tt0073486","tt0099685","tt0047478","tt0317248",
    "tt0114369","tt0102926","tt0816692","tt0245429","tt0120586",
    "tt0118799","tt0114814","tt6751668","tt0253474","tt1345836",
    "tt0172495","tt0482571","tt0407887","tt0078788","tt0208092",
    "tt0047396","tt0057012","tt0364569","tt0361748","tt0209144",
    "tt1853728","tt0105236","tt0119217","tt4154796","tt4154756",
    "tt0338013","tt0910970","tt2582802","tt1255953","tt0435761",
    "tt0986264","tt3783958","tt1049413","tt2380307","tt0120689",
    "tt0082971","tt0119698","tt0112573","tt0266697","tt1675434",
    "tt0405094","tt3011894","tt2106476","tt0198781","tt1187043",
    "tt0077416","tt0095327","tt0056172","tt1832382","tt0457430",
    "tt0944947","tt0903747","tt0795176","tt1475582","tt0306414",
    "tt1536537","tt0386676","tt2861424","tt2442560","tt1190634",
    "tt4574334","tt5180504","tt0108778","tt0411008","tt0460681",
    "tt1520211","tt3107288","tt2467372","tt1748166","tt0773262",
    "tt2802850","tt3749900","tt6468322","tt7366338","tt0455275",
    "tt1830617","tt2707408","tt3032476","tt1844624","tt2356777",
    "tt0112159","tt0098904","tt0121955","tt0141842","tt3581920",
    # 2022
    "tt1649418","tt10954984","tt9764362","tt6710474","tt3480822",
    "tt14564728","tt11989872","tt9052786","tt8760708","tt7740496",
    "tt9114286","tt15239678","tt8093700","tt11235196","tt13833688",
    "tt10838180","tt9603212","tt14513804","tt11851548","tt8367814",
    # 2023
    "tt9362722","tt15398776","tt5726616","tt17351924","tt9663764",
    "tt14230388","tt6791350","tt13016388","tt12037194","tt11847842",
    "tt21235248","tt15671028","tt15009428","tt14513596","tt10545296",
    "tt13669038","tt17526714","tt14230458","tt11286314","tt13238346",
    "tt16366836","tt10954600","tt14796836","tt15671028","tt9603212",
    "tt8323668","tt15251316","tt14230388","tt17351924","tt21807222",
    # 2024
    "tt17526714","tt21807222","tt12037194","tt13016388","tt14513596",
    "tt28015403","tt21692408","tt22687790","tt26753003","tt15671028",
    "tt13458214","tt14513804","tt29143234","tt21692408","tt26336086",
    "tt14513596","tt28215930","tt27534307","tt23676838","tt21698216",
    "tt13610936","tt14782226","tt22022452","tt21692408","tt26435070",
    "tt28026473","tt15671028","tt22022452","tt29580183","tt21353570",
]

GENRE_TRANSLATE = {
    "Action":"Боевик","Adventure":"Приключения","Animation":"Анимация",
    "Biography":"Биография","Comedy":"Комедия","Crime":"Криминал",
    "Documentary":"Документальный","Drama":"Драма","Family":"Семейный",
    "Fantasy":"Фэнтези","History":"История","Horror":"Ужасы",
    "Music":"Музыка","Musical":"Мюзикл","Mystery":"Мистика",
    "Romance":"Романтика","Sci-Fi":"Фантастика","Sport":"Спорт",
    "Thriller":"Триллер","War":"Война","Western":"Вестерн",
}

def translate(text: str) -> str:
    try:
        return GoogleTranslator(source="en", target="ru").translate(text)
    except Exception:
        return text

def fetch_movie(imdb_id: str) -> dict | None:
    try:
        r = requests.get(OMDB_BASE, params={"i": imdb_id, "apikey": OMDB_API_KEY}, timeout=10)
        data = r.json()
        if data.get("Response") == "True":
            return data
    except Exception as e:
        logger.error(f"OMDb error: {e}")
    return None

def build_message(data: dict) -> str:
    title_en = data.get("Title", "")
    title_ru = translate(title_en) if title_en else "Без названия"
    year = data.get("Year", "")
    plot_en = data.get("Plot", "")
    plot = translate(plot_en) if plot_en and plot_en != "N/A" else "Описание отсутствует."
    media = data.get("Type", "movie")
    rating = data.get("imdbRating", "N/A")
    votes = data.get("imdbVotes", "N/A")

    is_movie = media != "series"
    media_hashtag = "#фильм" if is_movie else "#сериал"

    genres_raw = [g.strip() for g in data.get("Genre", "").split(",")]
    genre_hashtags = " ".join(
        f"#{GENRE_TRANSLATE.get(g, g).replace(' ', '_')}"
        for g in genres_raw if g
    )

    try:
        stars = "⭐" * round(float(rating) / 2)
    except ValueError:
        stars = ""
    rating_str = f"{rating}/10" if rating != "N/A" else "нет оценки"

    kp_link = f"https://www.kinopoisk.ru/index.php?kp_query={quote(title_ru)}"

    return (
        f"🎬 <b>{title_ru}</b> ({year})\n\n"
        f"📖 {plot}\n\n"
        f"{stars} <b>Рейтинг IMDb:</b> {rating_str} ({votes} голосов)\n\n"
        f"🔍 <a href=\"{kp_link}\">Найти на Кинопоиске</a>\n\n"
        f"{media_hashtag} {genre_hashtags}"
    )

async def post_random_movie(bot: Bot, reply_chat_id: int | None = None):
    for _ in range(10):
        imdb_id = random.choice(IMDB_IDS)
        data = fetch_movie(imdb_id)
        if not data:
            continue

        text = build_message(data)
        title = data.get("Title", "")
        poster = data.get("Poster", "")

        if poster and poster != "N/A":
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=poster,
                caption=text,
                parse_mode=ParseMode.HTML,
            )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode=ParseMode.HTML,
            )

        logger.info(f"Опубликовано: {title}")
        if reply_chat_id:
            await bot.send_message(
                chat_id=reply_chat_id,
                text=f"✅ Опубликовано: <b>{translate(title)}</b>",
                parse_mode=ParseMode.HTML,
            )
        return

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👋 Привет! Доступные команды:\n\n"
        "/post — опубликовать фильм/сериал прямо сейчас\n"
        "/schedule — показать расписание постов на сегодня"
    )

async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У тебя нет доступа.")
        return
    await update.message.reply_text("⏳ Ищу случайный фильм/сериал...")
    await post_random_movie(context.bot, reply_chat_id=update.effective_chat.id)

async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    scheduler: AsyncIOScheduler = context.bot_data["scheduler"]
    jobs = sorted(
        [j for j in scheduler.get_jobs() if j.id.startswith("post_")],
        key=lambda j: j.next_run_time or 0,
    )
    if not jobs:
        await update.message.reply_text("Нет запланированных постов.")
        return
    lines = ["📅 <b>Расписание на сегодня:</b>\n"]
    for job in jobs:
        t = job.next_run_time.strftime("%H:%M") if job.next_run_time else "—"
        lines.append(f"• {t}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

def schedule_random_times(scheduler: AsyncIOScheduler, bot: Bot):
    posts_count = random.randint(2, 3)
    windows = [(8, 11), (13, 17), (19, 23)]
    chosen = random.sample(windows, posts_count)
    for hour_min, hour_max in chosen:
        hour = random.randint(hour_min, hour_max)
        minute = random.randint(0, 59)
        scheduler.add_job(
            post_random_movie,
            CronTrigger(hour=hour, minute=minute),
            args=[bot],
            id=f"post_{hour}_{minute}",
            replace_existing=True,
        )
        logger.info(f"Пост запланирован на {hour:02d}:{minute:02d}")

async def reschedule_daily(scheduler: AsyncIOScheduler, bot: Bot):
    for job in scheduler.get_jobs():
        if job.id.startswith("post_"):
            job.remove()
    schedule_random_times(scheduler, bot)

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("schedule", cmd_schedule))

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    app.bot_data["scheduler"] = scheduler

    schedule_random_times(scheduler, app.bot)
    scheduler.add_job(
        reschedule_daily,
        CronTrigger(hour=0, minute=1),
        args=[scheduler, app.bot],
        id="reschedule",
    )
    scheduler.start()

    logger.info("Бот запущен!")
    await app.run_polling()

# ✅ ФИКС — правильный запуск Python 3.13
if __name__ == "__main__":
    asyncio.run(main())
