import os
import MetaTrader5 as mt5
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import pandas as pd
import datetime

# Memuat variabel lingkungan dari file .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SYMBOL = os.getenv("SYMBOL")
TIMEFRAME = int(os.getenv("TIMEFRAME"))
ANALYSIS_INTERVAL = int(os.getenv("ANALYSIS_INTERVAL"))

# Variabel global untuk menyimpan waktu terakhir analisis
last_analysis_time = 0

# --- Bagian Peringatan Berita ---
# Daftar tanggal berita penting yang akan datang
# Perbarui daftar ini secara manual sesuai kalender ekonomi
upcoming_news = [
    datetime.date(2025, 8, 28), # Contoh: Non-Farm Payroll
    datetime.date(2025, 9, 5)   # Contoh: Keputusan suku bunga
]

def check_for_news():
    """Memeriksa apakah ada berita penting yang akan datang hari ini."""
    today = datetime.date.today()
    if today in upcoming_news:
        return True
    return False

# Fungsi untuk terhubung ke terminal MT5
def connect_to_mt5():
    """Menginisialisasi koneksi ke terminal MT5."""
    if not mt5.initialize():
        print("Inisialisasi MT5 gagal, error code =", mt5.last_error())
        return False
    print("Koneksi ke MT5 berhasil!")
    return True

# Fungsi untuk mengambil data historis dan menghitung indikator
def get_technical_analysis_data(symbol, timeframe, bars):
    """
    Mengambil data harga dari MT5 dan menghitung indikator.
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        print(f"Gagal mengambil data untuk {symbol}. Error: {mt5.last_error()}")
        return None
    
    rates_frame = pd.DataFrame(rates)
    rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
    
    # Perhitungan MA (Simple Moving Average)
    rates_frame['MA50'] = rates_frame['close'].rolling(window=50).mean()
    rates_frame['MA200'] = rates_frame['close'].rolling(window=200).mean()
    
    # Perhitungan RSI
    delta = rates_frame['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=14-1, min_periods=14).mean()
    avg_loss = loss.ewm(com=14-1, min_periods=14).mean()
    rs = avg_gain / avg_loss
    rates_frame['RSI'] = 100 - (100 / (1 + rs))

    return rates_frame

# Fungsi untuk membuat pesan analisis
def create_analysis_message(rates_frame, symbol):
    """
    Membuat pesan hasil analisis teknikal dengan logika lanjutan.
    """
    if rates_frame is None or len(rates_frame) < 200:
        return "Gagal mendapatkan data yang cukup untuk analisis."

    latest_data = rates_frame.iloc[-1]
    ma50 = latest_data['MA50']
    ma200 = latest_data['MA200']
    rsi = latest_data['RSI']
    current_price = mt5.symbol_info_tick(symbol).last
    
    # --- Logika Analisis Lanjutan ---
    signal = ""
    analysis_text = ""

    # Filter tren jangka panjang dengan MA200
    if current_price > ma200:
        # Tren naik (bullish), hanya cari sinyal beli
        analysis_text += "Tren Jangka Panjang: Naik (Harga di atas MA200)\n"
        # Sinyal beli: MA50 di atas MA200 DAN RSI tidak overbought
        if ma50 > ma200 and rsi < 70:
            signal = "BUY"
            analysis_text += "Sinyal Beli Ditemukan: MA50 > MA200 dan RSI normal."
        else:
            analysis_text += "Sinyal Beli Belum Terkonfirmasi."
    elif current_price < ma200:
        # Tren turun (bearish), hanya cari sinyal jual
        analysis_text += "Tren Jangka Panjang: Turun (Harga di bawah MA200)\n"
        # Sinyal jual: MA50 di bawah MA200 DAN RSI tidak oversold
        if ma50 < ma200 and rsi > 30:
            signal = "SELL"
            analysis_text += "Sinyal Jual Ditemukan: MA50 < MA200 dan RSI normal."
        else:
            analysis_text += "Sinyal Jual Belum Terkonfirmasi."
    else:
        # Pasar sideways atau tidak jelas
        analysis_text += "Tren Jangka Panjang: Sideways (Harga dekat MA200)\n"
        analysis_text += "Tidak ada sinyal yang jelas saat ini."

    # Periksa kondisi RSI
    if rsi > 70:
        analysis_text += f"\nKondisi RSI: Jenuh Beli (Overbought) di {rsi:.2f}"
    elif rsi < 30:
        analysis_text += f"\nKondisi RSI: Jenuh Jual (Oversold) di {rsi:.2f}"
    else:
        analysis_text += f"\nKondisi RSI: Netral di {rsi:.2f}"

    # Buat pesan akhir
    message = (
        f"📊 **Analisis untuk {symbol} ({mt5.timeframe_to_string(TIMEFRAME)})**\n\n"
        f"Harga Saat Ini: `{current_price:.5f}`\n"
        f"MA(50): `{ma50:.5f}`\n"
        f"MA(200): `{ma200:.5f}`\n"
        f"RSI(14): `{rsi:.2f}`\n\n"
        f"**Sinyal Teridentifikasi:** `{signal if signal else 'TIDAK ADA'}`\n\n"
        f"{analysis_text}"
    )

    return message

# --- Fungsi-fungsi Handler Bot Telegram ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengirim pesan sambutan saat perintah /start dipanggil."""
    await update.message.reply_text("Halo! Selamat datang di bot analisis teknikal.")
    # Di sini kita bisa menambahkan tombol untuk memilih simbol, dll.

async def analyse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Melakukan analisis dan mengirimkan hasilnya."""
    global last_analysis_time
    chat_id = update.effective_chat.id

    # Memeriksa peringatan berita
    if check_for_news():
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ **PERINGATAN BERITA PENTING!**\n"
                 "Hari ini ada berita ekonomi berdampak tinggi. Mohon berhati-hati, "
                 "hindari trading atau tunggu setelah rilis berita."
        )
        return

    # Mencegah spam dengan batasan waktu
    current_time = time.time()
    if current_time - last_analysis_time < ANALYSIS_INTERVAL:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Analisis terakhir dilakukan kurang dari {ANALYSIS_INTERVAL} detik lalu. Mohon tunggu."
        )
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text="Sedang melakukan analisis teknikal lanjutan. Mohon tunggu sebentar..."
    )

    # Dapatkan data
    rates_df = get_technical_analysis_data(SYMBOL, TIMEFRAME, 250)
    
    # Buat dan kirim pesan
    message = create_analysis_message(rates_df, SYMBOL)
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode='Markdown'
    )
    
    last_analysis_time = current_time

# Fungsi utama untuk menjalankan bot
def main():
    """Menjalankan bot Telegram."""
    if not connect_to_mt5():
        return
        
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Menambahkan handler
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("analyse", analyse_command))
    
    print("Bot Telegram siap. Kirim /start atau /analyse di chat untuk memulai.")
    
    application.run_polling()

if __name__ == '__main__':
    main()

