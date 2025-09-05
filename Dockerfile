# 1. Imagem Base
FROM python:3.11-slim

# 2. Configura o locale pt_BR.UTF-8 para o sistema
RUN apt-get update && apt-get install -y locales && \
    sed -i -e 's/# pt_BR.UTF-8 UTF-8/pt_BR.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales
ENV LANG pt_BR.UTF-8
ENV LANGUAGE pt_BR:pt
ENV LC_ALL pt_BR.UTF-8

# 3. Dependências de Sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    && rm -rf /var/lib/apt/lists/*

# 4. Diretório de Trabalho
WORKDIR /app

# 5. Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Código da Aplicação
COPY . .

# 7. Expondo a Porta
EXPOSE 8501

# 8. Comando de Execução
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]