FROM python:3.11-slim-buster

WORKDIR /app

COPY . /app

RUN pip install pipenv \
    && pipenv install --system

# Grant access to docker.sock to allow container parallelism
VOLUME /var/run/docker.sock

EXPOSE 5000

CMD ["python", "app.py"]