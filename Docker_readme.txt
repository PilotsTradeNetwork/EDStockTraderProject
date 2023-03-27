# To build a new docker image

$ docker build -t yourname/stockbot:2.1 .

# To run in a container

Make a local dir to store your .env and .carriers files

$ mkdir /opt/stockbot

$ cp .env .carriers /opt/stockbot

Run the container:

$ docker run -d --restart unless-stopped --name stockbot -e ENV_DIR='/data' -v /opt/stockbot:/data durzo/stockbot:2.1
