#!/bin/bash
# Amına koduğum root olarak çalışınca sapıtıyor --user parametreside problemli
source /home/sezer/panel/venv/bin/activate

# Steam ve Dc için GUI parametresi
export DISPLAY=:0
export XAUTHORITY=/home/sezer/.Xauthority

# Amına soktuğum elle yazınca çalışıyorsun servis olarak çalışınca mı götü başı dağıtıyorsun
exec python server.py --port 5001
