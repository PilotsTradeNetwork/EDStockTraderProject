FROM python:3.10-slim-buster
RUN mkdir -p /usr/src/bot
WORKDIR /usr/src/bot
COPY bot.py .
COPY requirements.txt .
RUN pip3 install -r requirements.txt
ENTRYPOINT [ "python3", "bot.py" ]
