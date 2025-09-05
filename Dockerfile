# 1. Imagem Base: Começamos com uma imagem oficial e leve do Python 3.11.
FROM python:3.11-slim

# 2. Dependências de Sistema: Usamos um comando mais robusto.
#    - DEBIAN_FRONTEND=noninteractive: Evita que a instalação peça qualquer input.
#    - Adicionamos o repositório 'contrib' para encontrar pacotes de fontes.
#    - Pré-aceitamos a licença das fontes da Microsoft para uma instalação automática.
RUN apt-get update && \
    apt-get install -y gnupg wget && \
    echo "deb http://deb.debian.org/debian bookworm contrib" >> /etc/apt/sources.list && \
    apt-get update && \
    echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections && \
    apt-get install -y --no-install-recommends \
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
    ttf-mscorefonts-installer \
    && rm -rf /var/lib/apt/lists/*

# 3. Diretório de Trabalho
WORKDIR /app

# 4. Copiamos e Instalamos as Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiamos o Restante da Aplicação
COPY . .

# 6. Expondo a Porta
EXPOSE 8501

# 7. Comando de Execução
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]