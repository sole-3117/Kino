# Xatolarni ko'rsatish uchun logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Bot ishga tushmoqda...")
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN topilmadi!")
            return
        
        application = Application.builder().token(BOT_TOKEN).build()

        # Buyruqlar uchun handlerlar
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('add', add_movie_cmd))
        application.add_handler(CommandHandler('delete', delete_movie_cmd))
        application.add_handler(CommandHandler('broadcast', broadcast_cmd))
        application.add_handler(CommandHandler('stats', stats_cmd))
        application.add_handler(CommandHandler('set_fsub', set_fsub_cmd))
        application.add_handler(CommandHandler('set_ad', set_ad_cmd))
        
        # Xabarlar uchun handlerlar
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )
        application.add_handler(
            CallbackQueryHandler(check_sub_callback, pattern='check_sub')
        )

        # Schedulerni ishga tushirish
        scheduler.add_job(reset_daily_ads, CronTrigger(hour=0, minute=0))
        schedule_ads(application)

        logger.info("Bot muvaffaqiyatli ishga tushdi!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}", exc_info=True)
    finally:
        scheduler.shutdown()
        logger.info("Bot to'xtatildi")

if __name__ == '__main__':
    main()
