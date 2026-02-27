#!/usr/bin/env bash
# THE MASTER TRANSMITTER
# This process connects to Owncast and NEVER exits.
# It listens on UDP for video from the Worker.
# Bed music plays continuously as the carrier wave.

set -uo pipefail

STREAM_URL="${STREAM_URL:-rtmp://localhost:1935/live/abc123}"
BED_MUSIC="/home/remvelchio/agent/assets/bed_22050.wav"
UDP_PORT="udp://127.0.0.1:10000?fifo_size=1000000&overrun_nonfatal=1"

TICKER_FILE="/home/remvelchio/agent/tmp/ticker_scroll.txt"
TICKER_FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

echo "$(date): MASTER TRANSMITTER STARTING"
echo "$(date): Listening on UDP 10000, streaming to $STREAM_URL"
echo "$(date): Bed music: $BED_MUSIC"

[[ -f "$TICKER_FILE" ]] || echo "AINN LIVE" > "$TICKER_FILE"

while true; do
    ffmpeg -hide_banner -loglevel warning -stats \
        -err_detect ignore_err \
        -fflags +genpts+igndts+discardcorrupt \
        -use_wallclock_as_timestamps 1 \
        -thread_queue_size 2048 -f mpegts -i "$UDP_PORT" \
        -stream_loop -1 -i "$BED_MUSIC" \
        -filter_complex \
            "[0:v]setpts=PTS-STARTPTS,fps=30,drawbox=x=0:y=h-60:w=iw:h=60:color=black@0.55:t=fill,drawtext=fontfile=${TICKER_FONT}:textfile=${TICKER_FILE}:reload=1:expansion=none:fontcolor=white:fontsize=28:x=w-mod(t*120\,(w+tw)):y=h-60+14:shadowcolor=black@0.6:shadowx=2:shadowy=2[v];[0:a]volume=1.0[story];[1:a]volume=0.08[bed];[story][bed]amix=inputs=2:duration=first:dropout_transition=0[a]" \
        -map "[v]" -map "[a]" \
        -c:v libx264 -preset veryfast -b:v 2500k -maxrate 2500k -bufsize 5000k \
        -pix_fmt yuv420p -g 60 -keyint_min 60 -sc_threshold 0 \
        -c:a aac -b:a 64k -ar 22050 -ac 1 \
        -f flv "$STREAM_URL" 2>>/home/remvelchio/agent/tmp/master.log || true

    echo "$(date): MASTER DIED — restarting in 2 seconds..."
    sleep 2
done
