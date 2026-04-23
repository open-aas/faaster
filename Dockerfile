FROM python:3.12.2-slim

RUN apt update -y && apt upgrade -y

RUN pip install poetry

WORKDIR /app

ADD . .

RUN poetry config virtualenvs.create false && poetry install --no-root --only system

EXPOSE 4840

ENTRYPOINT ["python", "server.py"]
