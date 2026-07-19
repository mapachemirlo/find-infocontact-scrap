# Imagen liviana de Python
FROM python:3.12-slim

# No generar .pyc y mostrar logs en vivo (sin buffer)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias primero (aprovecha la cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del codigo (scraper + api)
COPY . .

# La API escucha en el puerto 8000 dentro del contenedor
EXPOSE 8000

# Arrancar el servidor web que sirve la API
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
