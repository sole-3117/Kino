import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

DB_PATH = os.getenv('DB_PATH', 'database.db')
BACKUP_DIR = 'backups'

def ensure_backup_dir():
    """Backup papkasini yaratish"""
    Path(BACKUP_DIR).mkdir(exist_ok=True)

def create_backup():
    """Database backup yaratish - ZIP formatida"""
    ensure_backup_dir()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"{BACKUP_DIR}/backup_{timestamp}.zip"
    
    try:
        with zipfile.ZipFile(backup_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists(DB_PATH):
                zipf.write(DB_PATH, arcname='database.db')
        
        print(f"✅ Backup yaratildi: {backup_filename}")
        return backup_filename
    
    except Exception as e:
        print(f"❌ Backup xato: {e}")
        return None

def restore_backup(backup_file):
    """Backup'dan restore qilish"""
    try:
        with zipfile.ZipFile(backup_file, 'r') as zipf:
            # Eski database'ni backup qilish
            if os.path.exists(DB_PATH):
                backup_old = f"{DB_PATH}.old_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy(DB_PATH, backup_old)
                print(f"ℹ️ Eski database saqlandi: {backup_old}")
            
            # Yangi database extract qilish
            zipf.extract('database.db', '.')
        
        print(f"✅ Restore muvaffaqiyatli: {backup_file}")
        return True
    
    except Exception as e:
        print(f"❌ Restore xato: {e}")
        return False

def list_backups():
    """Barcha backuplar ro'yxati"""
    ensure_backup_dir()
    
    backups = sorted(Path(BACKUP_DIR).glob('backup_*.zip'), reverse=True)
    
    if not backups:
        print("Backuplar topilmadi")
        return []
    
    print(f"📦 Jami {len(backups)} ta backup:")
    for i, backup in enumerate(backups, 1):
        size = os.path.getsize(backup) / 1024  # KB
        mtime = datetime.fromtimestamp(os.path.getmtime(backup))
        print(f"{i}. {backup.name} ({size:.1f} KB) - {mtime}")
    
    return backups

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'create':
            create_backup()
        elif sys.argv[1] == 'restore' and len(sys.argv) > 2:
            restore_backup(sys.argv[2])
        elif sys.argv[1] == 'list':
            list_backups()
    else:
        print("""
Backup & Restore Utility

Ishlatish:
  python backup_restore.py create       - yangi backup yaratish
  python backup_restore.py restore FAYL  - backup'dan restore qilish
  python backup_restore.py list         - backuplar ro'yxati
""")
