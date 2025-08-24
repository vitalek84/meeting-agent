FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    psmisc \
    procps \
    wget \
    curl\
    unzip\
    git\
    gnupg\
    xdg-utils \
    xvfb \
    ffmpeg \
    curl \
    bash \
    software-properties-common \
    dbus-x11 \
    dbus-user-session \
    x11vnc \
    x11-utils \
    pipewire \
    pipewire-pulse \
    wireplumber \
    pipewire-audio-client-libraries \
    pulseaudio-utils \
    libportaudio2 \
    python3 python3-pip python3-dev \
    portaudio19-dev\
    sudo \
    pavucontrol \
    lsof \
    nano \
    python3-tk \
    python3-dev \
    nodejs \
    npm \
    gnome-screenshot \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN curl -sSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --no-binary :all: pyaudio --break-system-packages
COPY ./requirements.txt /requirements.txt
COPY ./wireplumber/restore-stream /root/.local/state/wireplumber/restore-stream
RUN chmod 444 /root/.local/state/wireplumber/restore-stream
RUN pip install -r requirements.txt --break-system-packages
# TODO COPY ALL DATA INTO CONTAINER!
COPY ./meeting_agent /app/src/meeting_agent
COPY ./worker_main.py /app/src/main.py
COPY ./meeting_agent_entrypoint.sh /app/src/entrypoint.sh
COPY ./mcp_config.json /app/src/mcp_config.json
COPY ./gm_control_elems /app/src/gm_control_elems
RUN chmod +x /app/src/entrypoint.sh
WORKDIR /app/src
CMD ["/app/src/entrypoint.sh"]

