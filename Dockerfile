# 1. Imagem Base: Começamos com uma imagem oficial e leve do Python 3.11.
FROM python:3.11-slim

# 2. Dependências de Sistema: Instalamos tudo que o Linux precisa para os PDFs e gráficos.
# Inclui bibliotecas para renderização de gráficos, fontes e texto.
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libatspi2.0-0 \
    fonts-liberation \
    fonts-dejavu \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 3. Diretório de Trabalho: Criamos uma pasta /app dentro do contêiner.
WORKDIR /app

# 4. Copiamos e Instalamos as Dependências Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiamos o Restante da Aplicação: app.py e os arquivos .xlsx.
COPY . .

# 6. Expondo a Porta: Informamos que a aplicação usará a porta 8501.
EXPOSE 8501

# 7. Comando de Execução: Este é o comando que inicia seu dashboard quando o contêiner roda.
# O --server.address=0.0.0.0 é essencial para que o app seja acessível de fora do contêiner.
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]