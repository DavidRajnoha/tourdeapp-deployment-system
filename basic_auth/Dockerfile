FROM python:3.11-slim-buster

WORKDIR /app

COPY . /app

# Setup entry point
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN pip install pipenv \
    && pipenv install --system --deploy

EXPOSE 5000

CMD ["/entrypoint.sh"]
