FROM python:3.11-slim-buster

WORKDIR /app

COPY . /app

ENV PYTHONPATH /app/src

# Setup entry point
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN pip install pipenv \
    && pipenv install --system --deploy

# Grant access to docker.sock to allow container parallelism
VOLUME /var/run/docker.sock

EXPOSE 5000

CMD ["/entrypoint.sh"]
