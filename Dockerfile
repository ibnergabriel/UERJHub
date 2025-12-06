# 1. Imagem base (Python leve)
FROM python:3.10-slim

# 2. Pasta de trabalho dentro do container
WORKDIR /app

# 3. Copia os requisitos e instala (para aproveitar cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia todo o código do projeto para dentro da imagem
COPY backend/ ./backend/

# 5. Cria a pasta de uploads para evitar erro de permissão
RUN mkdir -p backend/uploads

# 6. Define a pasta backend como diretório de execução
WORKDIR /app/backend

# 7. Comando para rodar o servidor
# host 0.0.0.0 é OBRIGATÓRIO no Docker para ser acessível de fora
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]