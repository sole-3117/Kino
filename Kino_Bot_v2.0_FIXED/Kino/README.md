# Kino Bot v2.0

Uzbek kinolarini ko'rish uchun Telegram boti.

## Xususiyatlari

- 🎬 Kinolar katalogi (kod/nom boʻyicha qidirish)
- 💳 Obuna rejalariga (1, 3, 6, 12 oylik)
- 💰 To'lov tizimi (Humo Card)
- ⭐ Reyting va sevimlilar
- 👥 Referral tizimi
- 🎁 Trial obuna (3 kun bepul)
- 📊 Admin paneli
- 🔄 Sync tizimi (ikkita bot orasida)
- 📦 Avtomatik backup (har 7 kun)

## O'rnatish (Lokal)

### 1. Repositoriyani klonlash

```bash
git clone https://github.com/sole-3117/Kino.git
cd Kino
```

### 2. Virtual environment yaratish

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# yoki
venv\Scripts\activate  # Windows
```

### 3. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 4. .env faylini yaratish

`.env.example` dan nusxa oling:

```bash
cp .env.example .env
```

va sozlang:

```
BOT_TOKEN=your_token_here
MAIN_ADMIN=your_user_id
DB_PATH=database.db
```

### 5. Botni ishga tushirish

```bash
python main.py
```

## Deploy (Koyeb)

### 1. GitHub repositoriyasi

Kodni GitHub'ga push qiling:

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Koyeb'da yangi deploy

- Koyeb.com'ga kirish
- "Create Service" bosamiz
- GitHub'dan `sole-3117/Kino` tanlash
- Environment variables oʻrnatasiz:
  - `BOT_TOKEN=...`
  - `MAIN_ADMIN=...`
  - `DB_PATH=database.db`
- Deploy qilish

### 3. Ikkinchi bot uchun

Xuddi shunday qadam, lekin:
- BOT_TOKEN ning boshqa tokeni
- Boshqa GitHub branch (opsional)

## Foydalanuvchi Interfeysi

### Asosiy Menyu

```
🎬 KINOLAR | 💳 OBUNA | 👤 PROFIL | ⚙️ SOZLAMALAR
```

### Kinolar

- 📝 Kod yozish (000001)
- 🔍 Nom yozish
- ❤️ Sevimlilar
- ⭐ Reyting

### Obuna

- 💰 Rejalar va narxlar
- 🎟️ Promo-kod
- 🎁 Trial (3 kun)
- 👥 Referral

### Profil

- 📈 Statistika
- 💬 Taklif
- 🆘 Admin murojaat

## Admin Buyruqlari

```
/add - kino qoʻshish (7 bosqich)
/delete - kino oʻchirish
/broadcast - hammaga xabar
/user_send - bitta foydalanuvchi
/block/unblock - bloklash
/sub_manage - obunani uzaytirish
/promo_admin - promo-kodlar
/stats - statistika
/settings - sozlamalar
/addadmin - admin qoʻshish (faqat bosh admin)
/backup - backup yaratish
```

## Database Schema

18 jadval:
- users
- subscriptions
- movies
- movie_ratings
- favorites
- user_watch_history
- promo_codes
- promo_uses
- pending_payments
- offers
- admin_requests
- bot_version
- settings
- admins
- movie_code_counter
- mandatory_subscriptions
- trial_subscriptions
- referrals

## Backup & Restore

### Backup yaratish

```bash
python backup_restore.py create
```

### Restore qilish

```bash
python backup_restore.py restore backups/backup_20240101_120000.zip
```

### Backuplar ro'yxati

```bash
python backup_restore.py list
```

## Xavfsizlik

- `.env` faylini `.gitignore`'ga kiritilgan
- Tokenlar muhim ma'lumot (GitHub'ga yuklama!)
- Admin bypass: `is_admin()` MAIN_ADMIN + admins DB tekshiradi
- SQLite injection'dan himoya mavjud (parameterized queries)

## Muammolarni hal qilish

### Bot ishga tushmistaydigan bo'lsa

```bash
# Token tekshiring
echo $BOT_TOKEN

# Database'ni init qilish
python -c "import db; db.init_db()"

# Loglarni qarang
python main.py
```

### Database kilit muammosi

Agar ikki bot bir paytda ishlatsa, SQLite tikilishi mumkin:
- `database.db` har bir bot uchun alohida bo'lishi kerak
- `DB_PATH` environment variable'da boshqarilib turibdi

### Video yuborishda xato

- Video file_id to'g'riligini tekshiring
- Telegram'da video sifatini tekshiring (max 2GB)

## Litsenziya

MIT License

## Muallif

Solejon Adashov  
Samarqand, Uzbekistan  
**GitHub:** [@sole-3117](https://github.com/sole-3117)

---

**Bot:** [@kinobotuzbot](https://t.me/kinobotuzbot)

**Kanal:** [@kinobot_v2](https://t.me/kinobot_v2)

**Versiya:** v2.0  
**Yangilandi:** 2024
