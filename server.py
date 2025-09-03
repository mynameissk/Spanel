from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import subprocess
import psutil
import threading
import time
import logging

# Siktiğimin login ayarı
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

def system_stats_thread():
    """Sistem durum kontrol amk"""
    while True:
        try:
            # CPU kullanımı
            cpu = psutil.cpu_percent(interval=None)
            # Ram kullanımı
            ram = psutil.virtual_memory().percent

            logger.debug(f"CPU: {cpu}%, RAM: {ram}%")

            # İstemcilere sistem güncellemesi gönderme
            socketio.emit("system_update", {"cpu": cpu, "ram": ram})

            # Şu anda çalan müziği alma kısmı
            title = "Duraklatıldı"
            try:
                # Aktif playerları al
                players = subprocess.check_output(["playerctl", "-l"], stderr=subprocess.DEVNULL).decode().splitlines()
                if players:
                    # İlk aktif player üzerinden şarkı başlığı alma
                    title = subprocess.check_output(["playerctl", "-p", players[0], "metadata", "title"],
                                                  stderr=subprocess.DEVNULL,
                                                  timeout=2).decode().strip()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.debug(f"Playerctl hata: {e}")

            socketio.emit("now_playing", {"title": title})

            # Bu sikiği koymazsam götünde yarrak varmış gibi oluyor okunmuyo bile
            time.sleep(2)

        except Exception as e:
            logger.error(f"Sistem istatistikleri alınırken hata: {str(e)}")
            time.sleep(5)

# Thread başlat
try:
    stats_thread = threading.Thread(target=system_stats_thread, daemon=True)
    stats_thread.start()
    logger.info("Sistem izleme thread'i başlatıldı")
except Exception as e:
    logger.error(f"Thread başlatılamadı: {str(e)}")

#Bu kısımın amk
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/volume", methods=["POST"])
def volume():
    level = request.json.get("level")
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
    socketio.emit("volume_update", {"volume": level})
    return jsonify({"status": "ok", "volume": level})

@app.route("/mute", methods=["POST"])
def mute():
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    return jsonify({"status": "ok"})

@app.route("/playpause", methods=["POST"])
def playpause():
    subprocess.run(["playerctl", "play-pause"])
    return jsonify({"status": "ok"})

@app.route("/next", methods=["POST"])
def next_track():
    subprocess.run(["playerctl", "next"])
    return jsonify({"status": "ok"})

@app.route("/previous", methods=["POST"])
def previous_track():
    subprocess.run(["playerctl", "previous"])
    return jsonify({"status": "ok"})

@app.route("/launch", methods=["POST"])
def launch():
    app_name = request.json.get("app")
    commands = {
        "google": ["google-chrome-stable"],#Bunda sorun yaşarım dedim en kolay bu çalıştı amk
        "steam": ["/usr/bin/steam"], #Şu siktiğimin piçi root haklarıyla çalışmıyor
        "discord": ["flatpak", "run", "com.discordapp.Discord"],#Buda öyle
        "spotify": ["spotify"],
        "youtube": ["youtube"]
    }
    if app_name in commands:
        subprocess.Popen(commands[app_name])
        return jsonify({"status": "ok", "app": app_name})
    return jsonify({"status": "error", "msg": "Unknown app"}), 400

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, allow_unsafe_werkzeug=True)


