# start from base
FROM ubuntu:20.04

LABEL maintainer="Prakhar Srivastav <prakhar@prakhar.me>"

# install system-wide deps for python and node
RUN apt-get -yqq update
RUN apt-get -yqq install python3-pip python3-dev curl gnupg
RUN curl -sL https://deb.nodesource.com/setup_10.x | bash
RUN apt-get install -yq nodejs

# copy our application code
ADD flask-app /opt/flask-app
WORKDIR /opt/flask-app

# fetch app specific deps
RUN npm install
RUN npm run build
RUN pip3 install -r requirements.txt
RUN pip3 install opentelemetry-distro
RUN pip3 install opentelemetry-exporter-otlp
RUN opentelemetry-bootstrap --action=install

# expose port
EXPOSE 5000

# start app
CMD [ "python3", "./app.py" ]
