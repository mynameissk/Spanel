from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import subprocess
import psutil
import threading
import time
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
#Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

previous_title = None
current_position = 0.0
current_duration = 0.0
is_playing = False
lock = threading.Lock()

def format_time(seconds):
    if not seconds or seconds == "N/A":
        return "00:00"
    try:
        seconds = float(seconds)
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    except:
        return "00:00"

def system_stats_thread():
    global previous_title, current_position, current_duration, is_playing
    while True:
        try:
            # CPU ve RAM
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            socketio.emit("system_update", {"cpu": cpu, "ram": ram})

            title = "Duraklatıldı"
            duration = "00:00"
            position_percent = 0

            with lock:
                try:
                    players = subprocess.check_output(["playerctl", "-l"], stderr=subprocess.DEVNULL).decode().splitlines()
                    if players:
                        # Çalma durumu
                        status = subprocess.check_output(
                            ["playerctl", "-p", players[0], "status"],
                            stderr=subprocess.DEVNULL,
                            timeout=2
                        ).decode().strip()
                        is_playing = status == "Playing"

                        # Başlık
                        title_raw = subprocess.check_output(
                            ["playerctl", "-p", players[0], "metadata", "title"],
                            stderr=subprocess.DEVNULL,
                            timeout=2
                        ).decode().strip()
                        title = title_raw if title_raw else title

                        # Süre
                        dur_us = subprocess.check_output(
                            ["playerctl", "-p", players[0], "metadata", "mpris:length"],
                            stderr=subprocess.DEVNULL,
                            timeout=2
                        ).decode().strip()
                        if dur_us.isdigit():
                            current_duration = int(dur_us) / 1_000_000
                            duration = format_time(current_duration)
                        else:
                            current_duration = 0

                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                    logger.debug(f"Playerctl hata: {e}")
                    is_playing = False
                    current_position = 0
                    current_duration = 0
                    previous_title = None

                # Şarkı pozisyon sıfırla
                if title != previous_title:
                    current_position = 0.0
                    previous_title = title

                # Pozisyon kaydır
                if is_playing and current_duration > 0:
                    current_position += 1
                    if current_position >= current_duration:
                        current_position = 0.0
                position = format_time(current_position)
                position_percent = min(100, max(0, (current_position / current_duration) * 100)) if current_duration > 0 else 0

            socketio.emit("now_playing", {
                "title": title,
                "position": position,
                "duration": duration,
                "position_percent": position_percent,
                "is_playing": is_playing
            })

            time.sleep(1)
        except Exception as e:
            logger.error(f"Sistem istatistikleri alınırken hata: {str(e)}")
            time.sleep(5)

# Thread başlat
try:
    stats_thread = threading.Thread(target=system_stats_thread, daemon=True)
    stats_thread.start()
except Exception as e:
    logger.error(f"Thread başlatılamadı: {str(e)}")

# Flask
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
    global previous_title, current_position
    previous_title = None
    current_position = 0
    subprocess.run(["playerctl", "next"])
    return jsonify({"status": "ok"})

@app.route("/previous", methods=["POST"])
def previous_track():
    global previous_title, current_position
    previous_title = None
    current_position = 0
    subprocess.run(["playerctl", "previous"])
    return jsonify({"status": "ok"})

@app.route("/seek", methods=["POST"])
def seek():
    pos = request.json.get("position", 0)
    try:
        players = subprocess.check_output(["playerctl", "-l"], stderr=subprocess.DEVNULL).decode().splitlines()
        if players and current_duration > 0:
            target = current_duration * float(pos)
            subprocess.run(["playerctl", "-p", players[0], "position", str(target)])
            with lock:
                global current_position
                current_position = target
        return jsonify({"status": "ok", "position": pos})
    except Exception as e:
        logger.error(f"Seek hatası: {str(e)}")
        return jsonify({"status": "error", "msg": str(e)}), 400

@app.route("/launch", methods=["POST"])
def launch():
    app_name = request.json.get("app")
    commands = {
        "google": ["google-chrome-stable"],
        "steam": ["/usr/bin/steam"],
        "discord": ["flatpak", "run", "com.discordapp.Discord"],
        "spotify": ["spotify"],
        "youtube": ["youtube"]
    }
    if app_name in commands:
        subprocess.Popen(commands[app_name])
        return jsonify({"status": "ok", "app": app_name})
    return jsonify({"status": "error", "msg": "Unknown app"}), 400

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, allow_unsafe_werkzeug=True)
