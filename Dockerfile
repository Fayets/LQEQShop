FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8030
# --proxy-headers: sin eso el límite de intentos de login vería a todos con la IP del proxy
CMD ["sh", "-c", "python -m app.seed && python -m uvicorn app.main:app --host 0.0.0.0 --port 8030 --proxy-headers --forwarded-allow-ips '*'"]
