#!/bin/bash

mkdir -p /run/dbus
dbus-daemon --system --fork


# export DBUS_SESSION_BUS_ADDRESS=unix:abstract=/tmp/dbus-AqusXVb2Hw


export XDG_RUNTIME_DIR=/tmp
export PULSE_SERVER=/tmp/pulse/native
export DISPLAY=:0
# Start Xvfb in the background
echo "Setup Xvfb..."

Xvfb $DISPLAY -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
# Start x11vnc
echo "Setup x11vnc..."
x11vnc -display $DISPLAY -forever -noxdamage -shared -nopw -quiet &
sleep 2

echo "Ensuring /etc/machine-id exists..."
if [ ! -f /etc/machine-id ]; then
  dbus-uuidgen --ensure=/etc/machine-id
  if [ $? -ne 0 ]; then
      echo "Error: Failed to ensure /etc/machine-id exists."
      # Decide if this is fatal based on needs
      # exit 1
  fi
else
  echo "/etc/machine-id already exists."
fi
read machine_id < /etc/machine-id
echo "Launching DBus session..."
dbus_output=$(dbus-launch --autolaunch="$machine_id")
echo "$dbus_output"

while IFS='=' read -r var val; do
  # Remove leading/trailing whitespace (if any)
  var=$(echo "$var" | xargs)
  val=$(echo "$val" | xargs)
  export "$var=$val"
done <<< "$dbus_output"

printenv
# Start pipewire server
echo "Starting pipewire..."
pipewire &
pipewire-pulse &
sleep 2

pactl load-module module-null-sink \
  sink_name=virtual_sink_agent \
  format=s16le \
  rate=24000 \
  channels=1 \
  sink_properties=device.description=virtual_sink_agent

pactl load-module module-remap-source source_name=virtual_chrome_mic master=virtual_sink_agent.monitor


pactl load-module module-null-sink \
  sink_name=virtual_sink_chrome \
  format=s16le \
  rate=16000 \
  channels=1 \
  sink_properties=device.description=virtual_sink_chrome

pactl load-module module-remap-source source_name=virtual_agent_mic master=virtual_sink_chrome.monitor
sleep 2
wireplumber &
sleep 2

xauth generate :0 . trusted

# python3 worker_main.py

google-chrome --no-sandbox


