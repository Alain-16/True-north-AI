FROM python:3.12-slim

WORKDIR /app

COPY TrueNorth-AI/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "fastapi","run","TrueNorth-AI/main.py", "--host", "0.0.0.0", "--port", "8000" ]
