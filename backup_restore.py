import os
import zipfile
import shutil
import datetime
from telegram.ext import ContextTypes
import db

def create_backup_zip(zip_name: str = "backup.zip") -> str:
    db_path = db.DB_PATH
    if not os.path.exists(db_path):
        return ""
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(db_path, arcname="database.db")
    return zip_name

def restore_from_file(file_path: str) -> bool:
    try:
        if file_path.endswith(".zip"):
            with zipfile.ZipFile(file_path, 'r') as zipf:
                zipf.extract("database.db", ".")
            return True
        elif file_path.endswith(".db"):
            shutil.copyfile(file_path, db.DB_PATH)
            return True
    except Exception as e:
        print(f"Restore xatosi: {e}")
        return False
    return False

async def auto_backup_job(context: ContextTypes.DEFAULT_TYPE):
    main_admin = context.bot_data.get("MAIN_ADMIN")
    if not main_admin:
        return
    zip_name = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    created = create_backup_zip(zip_name)
    if created and os.path.exists(created):
        try:
            with open(created, "rb") as doc:
                await context.bot.send_document(
                    chat_id=main_admin,
                    document=doc,
                    caption=f"📦 <b>Avtomatik Zaxira (Backup)</b>\nSana: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    parse_mode="HTML"
                )
            os.remove(created)
        except Exception as e:
            print(f"Backup yuborishda xatolik: {e}")
            