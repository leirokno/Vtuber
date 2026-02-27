#!/usr/bin/env bash
# BROADCAST LAUNCHER
# Boots Master + Worker in a single tmux session with two panes.

set -uo pipefail

SESSION="broadcast"

# Kill any existing broadcast
tmux kill-session -t "$SESSION" 2>/dev/null
pkill -9 -f "master.sh" 2>/dev/null
pkill -9 -f "worker.sh" 2>/dev/null
pkill -9 -f "ffmpeg.*udp" 2>/dev/null
pkill -9 -f "ffmpeg.*rtmp" 2>/dev/null
sleep 2

# Clear logs
> /home/remvelchio/agent/tmp/master.log
> /home/remvelchio/agent/tmp/worker.log

# Create tmux session with Master in first pane
tmux new-session -d -s "$SESSION" -n "master" \
    "bash /home/remvelchio/agent/stream/master.sh 2>&1 | tee /home/remvelchio/agent/tmp/master_console.log"

# Wait for Master to start listening
sleep 5

# Add Worker in second pane
tmux split-window -t "$SESSION" -h \
    "bash /home/remvelchio/agent/stream/worker.sh 2>&1 | tee /home/remvelchio/agent/tmp/worker_console.log"

echo "$(date): Broadcast launched in tmux session '$SESSION'"
echo "  tmux attach -t $SESSION    # to monitor"
echo "  tmux kill-session -t $SESSION  # to stop"
