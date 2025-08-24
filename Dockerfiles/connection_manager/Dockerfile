FROM python:3.12-bookworm as prod
# RUN apt-get update && apt-get install -y \
#   gcc \
#   && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /requirements.txt
RUN pip install -r requirements.txt

COPY ./connection_manager /app/src/connection_manager
WORKDIR /app/src
ENV MANAGER_HOST=0.0.0.0
ENV MANAGER_PORT=8000

EXPOSE $MANAGER_PORT

# CMD ["uvicorn", "--host", $MANAGER_HOST, "--port", $MANAGER_PORT, "--log-level", "info", "connection_manager:app"]
CMD uvicorn --host $MANAGER_HOST --port $MANAGER_PORT --log-level info connection_manager:app

