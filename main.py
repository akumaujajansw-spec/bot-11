import os
import io
import time
import qrcode
import telebot
from flask import Flask, request, jsonify
import midtransclient
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Config Environment
TOKEN = os.getenv("BOT_TOKEN", "8834766580:AAG0F3PFIhRGdCJyIiNP7w-8hs4Hsx3e20I")
MIDTRANS_SERVER_KEY = os.getenv("MIDTRANS_SERVER_KEY", "Mid-server-pFVjkKnZS56RezFUtfuzbfLZ") # Ganti dengan Server Key Anda
IS_PRODUCTION = False # Ubah ke True jika sudah Live (bukan Sandbox)

# Inisialisasi Bot & Midtrans
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

core_api = midtransclient.CoreApi(
    is_production=IS_PRODUCTION,
    server_key=MIDTRANS_SERVER_KEY,
    client_key=os.getenv("MIDTRANS_CLIENT_KEY", "Mid-client-aAgS7XTQ8Vm1YQw5")
)

ALL_GROUP_IDS = [
    -1003721629607, -1003646177202, -1003727409464, -1003713991635,
    -1003839151133, -1003561794613, -1003634689467, -1003853297361,
    -1004451939488, -1004486985873, -1003813292350
]

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒 Beli Paket VIP 11 Grup (Rp 85.000)"))
    markup.add(KeyboardButton("⭐ Testimoni"), KeyboardButton("❓ Bantuan"))
    markup.add(KeyboardButton("📞 Hubungi Admin"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Halo! Selamat datang di bot WarungDosa.\n\n"
        "🔥 <b>Paket VIP:</b> Dapatkan akses ke <b>11 Grup VIP Sekaligus</b> hanya dengan <b>Rp 85.000</b>!\n\n"
        "Silakan gunakan menu di bawah untuk mulai:", 
        parse_mode="HTML", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "🛒 Beli Paket VIP 11 Grup (Rp 85.000)")
def handle_buy_menu(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 Buat QRIS Pembayaran", callback_data="generate_qris"))
    
    bot.send_message(
        chat_id,
        "Anda memilih <b>Paket VIP 11 Grup Sekaligus (Rp 85.000)</b>.\n\nKlik tombol di bawah untuk membuat QR Code pembayaran:",
        parse_mode="HTML",
        reply_markup=markup
    )

# --- GENERATE QRIS DINAMIS MIDTRANS ---
@bot.callback_query_handler(func=lambda call: call.data == "generate_qris")
def process_generate_qris(call):
    chat_id = call.message.chat.id
    bot.send_chat_action(chat_id, 'upload_photo')
    
    # Buat Order ID unik (gabungan User ID dan Timestamp)
    order_id = f"WD-VIP-{chat_id}-{int(time.time())}"
    
    param = {
        "payment_type": "qris",
        "transaction_details": {
            "gross_amount": 85000,
            "order_id": order_id
        },
        "qris": {
            "acquirer": "gopay" # Mendukung QRIS umum (Gopay/Shopee/DANA/dll)
        }
    }

    try:
        # Request Charge Ke Midtrans
        charge_response = core_api.charge(param)
        
        # Ambil QR string atau QR URL dari response
        qr_string = charge_response.get('qr_string')
        
        # Generasi gambar QR Code dari QR String
        qr_img = qrcode.make(qr_string)
        img_byte_arr = io.BytesIO()
        qr_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        caption_text = (
            f"💳 <b>QRIS Pembayaran Paket VIP</b>\n\n"
            f"<b>Total:</b> Rp 85.000\n"
            f"<b>Order ID:</b> <code>{order_id}</code>\n"
            f"<b>Batas Waktu:</b> 15 Menit\n\n"
            f"Silakan scan QR Code di atas menggunakan GoPay, OVO, DANA, ShopeePay, BCA, Mandiri, DLL.\n\n"
            f"⚡ <b>Setelah pembayaran berhasil, link grup akan terkirim secara otomatis!</b>"
        )
        
        bot.send_photo(
            chat_id, 
            photo=img_byte_arr, 
            caption=caption_text, 
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

    except Exception as e:
        bot.send_message(chat_id, f"Gagal membuat QRIS Pembayaran: {e}")

# --- WEBHOOK / NOTIFICATION HANDLER UNTUK MIDTRANS ---
@app.route('/', methods=['GET'])
def index():
    return "Server Bot Telegram & Webhook Midtrans Aktif!", 200
    
@app.route('/midtrans-webhook', methods=['POST'])
def midtrans_webhook():
    notification_body = request.get_json()
    
    try:
        # Verifikasi notifikasi menggunakan SDK
        status_response = core_api.transactions.notification(notification_body)
        
        order_id = status_response['order_id']
        transaction_status = status_response['transaction_status']
        fraud_status = status_response['fraud_status']

        # Ambil chat_id dari Order ID (Format: WD-VIP-{chat_id}-{timestamp})
        parts = order_id.split("-")
        target_user_id = int(parts[2])

        # Cek jika pembayaran sukses
        if transaction_status == 'settlement' or (transaction_status == 'capture' and fraud_status == 'accept'):
            
            # Generate Link 11 Grup
            generated_links = []
            for group_id in ALL_GROUP_IDS:
                invite = bot.create_chat_invite_link(chat_id=group_id, member_limit=1)
                generated_links.append(invite.invite_link)
            
            links_text = "\n".join([f"• {link}" for link in generated_links])
            
            # Kirim Pesan Akses Otomatis ke User
            bot.send_message(
                target_user_id,
                f"✅ <b>Pembayaran Berhasil Diterima!</b>\n\n"
                f"Berikut link akses ke 11 Grup VIP (Sekali Pakai):\n\n{links_text}\n\n"
                f"<b>Catatan:</b>\n"
                f"- Link hanya bisa digunakan 1 kali per grup.\n"
                f"- Jika link kedaluwarsa, artinya Anda sudah masuk ke grup.",
                parse_mode="HTML"
            )
            
        return jsonify({"status": "OK"}), 200

    except Exception as e:
        print(f"Error Webhook: {e}")
        return jsonify({"status": "Error", "message": str(e)}), 400

# Endpoint Jalankan Server & Bot
if __name__ == "__main__":
    import threading
    
    # Thread terpisah untuk bot polling
    threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True)).start()
    
    # Ambil Port dinamis dari Railway (Default 5000 untuk lokal)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
