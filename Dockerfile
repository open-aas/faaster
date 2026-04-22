FROM python:3.11.2-slim

RUN apt-get update -y && apt upgrade -y

WORKDIR /app

ADD . .

RUN pip install -r requirements-core.txt

EXPOSE 4840

ENTRYPOINT ["python", "server.py"]
