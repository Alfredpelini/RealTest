from dotenv import load_dotenv
load_dotenv()

import json
import os
import urllib.request
import urllib.parse
import time

# --- Ρυθμίσεις (Αλλάζεις μόνο εδώ) ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

ETHERSCAN_API_KEY = os.environ["ETHERSCAN_API_KEY"]
ETH_WALLET = os.environ["ETH_WALLET"]  # Το πορτοφόλι σου
REQUIRED_PAYMENT_AMOUNT = 0.0007  # ETH που πρέπει να πληρωθούν

ORDERS_FILE = "user_orders.json"
USED_TX_FILE = "used_tx_hashes.json"

waiting_for_tx = {}

# --- Φόρτωμα / Αποθήκευση δεδομένων ---
def load_json_file(filename, default):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    else:
        return default

def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f)

used_tx_hashes = set(load_json_file(USED_TX_FILE, []))
orders = load_json_file(ORDERS_FILE, {})

# --- Telegram API ---
def send_request(method, data):
    url = f"{API_URL}/{method}"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    encoded_data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=encoded_data, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"⚠️ Telegram API error: {e}")
        return {}

def send_text(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        data["reply_markup"] = json.dumps(keyboard)
    send_request("sendMessage", data)

def send_photo(chat_id, image_path, caption=""):
    if not os.path.exists(image_path):
        send_text(chat_id, "❌ Η εικόνα δεν βρέθηκε.")
        return
    url = f"{API_URL}/sendPhoto"
    with open(image_path, "rb") as photo:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        payload = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="{os.path.basename(image_path)}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + photo.read() + f"\r\n--{boundary}--\r\n".encode("utf-8")

        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        try:
            req = urllib.request.Request(url, data=payload, headers=headers)
            urllib.request.urlopen(req)
        except Exception as e:
            print(f"⚠️ Σφάλμα αποστολής φωτογραφίας: {e}")

# --- Μενού ---
def send_main_menu(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📍 Χαριλάου", "callback_data": "xarilaou"}],
            [{"text": "📍 Πυλαία", "callback_data": "pylaia"}],
            [{"text": "📍 Πανόραμα", "callback_data": "panorama"}],
            [{"text": "📍 Καλαμαριά", "callback_data": "kalamaria"}],
            [{"text": "📍 Μπότσαρη", "callback_data": "mpotsari"}],
            [{"text": "📍 Τούμπα", "callback_data": "toumpa"}],
            [{"text": "📞 Επικοινωνία", "callback_data": "contact"}]
        ]
    }
    send_text(chat_id, "🛍️ Καλώς ήρθες! Επέλεξε περιοχή:", keyboard)

def handle_category(chat_id, category):
    folder = f"images/{category}"
    if not os.path.exists(folder):
        send_text(chat_id, "⚠️ Η κατηγορία δεν βρέθηκε.")
        return
    files = [f for f in os.listdir(folder) if f.lower().endswith(".jpg")]
    if not files:
        send_text(chat_id, "⚠️ Δεν υπάρχουν προϊόντα σε αυτήν την κατηγορία.")
        return
    keyboard = {"inline_keyboard": []}
    for file in files:
        keyboard["inline_keyboard"].append(
            [{"text": file.replace('.jpg', ''), "callback_data": f"product_{category}_{file}"}]
        )
    keyboard["inline_keyboard"].append([{"text": "🔙 Επιστροφή", "callback_data": "main_menu"}])
    send_text(chat_id, f"📂 Επιλέξτε προϊόν από την περιοχή {category}:", keyboard)

def save_order(user_id, category, filename):
    global orders
    if user_id not in orders:
        orders[user_id] = []
    item = f"{category}/{filename}"
    if item not in orders[user_id]:
        orders[user_id].append(item)
    save_json_file(ORDERS_FILE, orders)

def handle_product_selection(chat_id, category, filename):
    image_path = f"images/{category}/{filename}"
    if not os.path.exists(image_path):
        send_text(chat_id, "❌ Το προϊόν δεν βρέθηκε.")
        return
    user_id = str(chat_id)
    save_order(user_id, category, filename)
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔙 Πίσω στο Μενού", "callback_data": "main_menu"}],
            [{"text": "💳 Πληρωμή με Crypto", "callback_data": "checkout"}]
        ]
    }
    send_text(chat_id, f"🛒 Το προϊόν *{filename.replace('.jpg','')}* προστέθηκε στο καλάθι σου.", keyboard)

def start_checkout(chat_id):
    user_id = str(chat_id)
    if user_id not in orders or not orders[user_id]:
        send_text(chat_id, "🛒 Δεν έχεις προϊόντα στο καλάθι σου. Πρόσθεσε πρώτα προϊόντα.")
        return

    keyboard = {
        "inline_keyboard": [
            [{"text": "❌ Ακύρωση Παραγγελίας", "callback_data": "cancel_order"}]
        ]
    }
    send_text(
        chat_id,
        f"💳 Στείλε το Transaction ID (Tx Hash) μετά τηv πληρωμή σου στο πορτοφόλι:\n`{ETH_WALLET}`\n\nΠρέπει να είναι πλήρης και έγκυρος.",
        keyboard
    )
    waiting_for_tx[chat_id] = True

def check_eth_payment(tx_hash):
    url = f"https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={ETHERSCAN_API_KEY}"
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            result = data.get("result")
            if not result:
                return False
            to_address = result.get("to")
            value_hex = result.get("value")
            if not to_address or not value_hex:
                return False
            if to_address.lower() != ETH_WALLET.lower():
                return False
            value_eth = int(value_hex, 16) / (10**18)
            if value_eth < REQUIRED_PAYMENT_AMOUNT:
                return False
            return True
    except Exception as e:
        print(f"⚠️ Σφάλμα ελέγχου πληρωμής: {e}")
        return False

def handle_payment_tx(chat_id, tx_hash):
    tx_hash = tx_hash.strip()
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        send_text(chat_id, "❌ Το Transaction ID φαίνεται μη έγκυρο. Προσπάθησε ξανά.")
        return
    if tx_hash in used_tx_hashes:
        send_text(chat_id, "⚠️ Το Transaction ID αυτό έχει ήδη χρησιμοποιηθεί.")
        return
    send_text(chat_id, "🔎 Ελέγχω το Transaction ID, παρακαλώ περίμενε...")
    if check_eth_payment(tx_hash):
        used_tx_hashes.add(tx_hash)
        save_json_file(USED_TX_FILE, list(used_tx_hashes))
        waiting_for_tx.pop(chat_id, None)
        send_photo(chat_id, "images/thank_you.jpg", "✅ Η πληρωμή επιβεβαιώθηκε. Ευχαριστούμε πολύ!")
        send_text(chat_id, "📦 Το προϊόν σου θα αποσταλεί σύντομα.")
        user_id = str(chat_id)
        orders[user_id] = []
        save_json_file(ORDERS_FILE, orders)
    else:
        send_text(chat_id, "❌ Η πληρωμή δεν βρέθηκε ή δεν αντιστοιχεί στο ποσό. Προσπάθησε ξανά.")

def answer_callback(callback_query_id, text=None, show_alert=False):
    data = {"callback_query_id": callback_query_id, "show_alert": show_alert}
    if text:
        data["text"] = text
    send_request("answerCallbackQuery", data)

# --- Διαχείριση Updates ---
def process_update(update):
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if chat_id in waiting_for_tx:
            handle_payment_tx(chat_id, text)
            return

        if text == "/start":
            send_main_menu(chat_id)
        else:
            send_text(chat_id, "Παρακαλώ επέλεξε από το μενού ή πάτησε /start για να ξεκινήσεις.")

    elif "callback_query" in update:
        callback = update["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        data = callback["data"]
        callback_id = callback["id"]

        if data == "main_menu":
            send_main_menu(chat_id)

        elif data in ["xarilaou", "pylaia", "panorama", "kalamaria", "mpotsari", "toumpa"]:
            handle_category(chat_id, data)

        elif data.startswith("product_"):
            parts = data.split("_", 2)
            if len(parts) == 3:
                category, filename = parts[1], parts[2]
                handle_product_selection(chat_id, category, filename)
            else:
                send_text(chat_id, "⚠️ Σφάλμα στο προϊόν.")

        elif data == "checkout":
            start_checkout(chat_id)

        elif data == "cancel_order":
            user_id = str(chat_id)
            orders[user_id] = []
            save_json_file(ORDERS_FILE, orders)
            waiting_for_tx.pop(chat_id, None)
            send_text(chat_id, "❌ Η παραγγελία σου ακυρώθηκε.")
            send_main_menu(chat_id)

        elif data == "contact":
            contact_text = (
                "📞 *Επικοινωνία Manager:* @BigmanGustavo\n\n"
                "✉️ Στείλε το μήνυμά σου εδώ, θα σου απαντήσουμε σύντομα."
            )
            send_text(chat_id, contact_text)

        answer_callback(callback_id)

# --- Main Loop ---
def main():
    offset = None
    print("🚀 Bot ξεκίνησε")
    while True:
        url = f"{API_URL}/getUpdates?timeout=30"
        if offset:
            url += f"&offset={offset}"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    process_update(update)
        except Exception as e:
            print(f"⚠️ Σφάλμα στο getUpdates: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
