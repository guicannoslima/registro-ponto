# ============================================================
# Etapa 1 (builder): compila as dependências Python em "wheels"
# ============================================================
FROM python:3.12-slim AS builder

# Ferramentas de compilação, usadas só nesta etapa (não vão para a imagem final).
# libcairo2-dev/pkg-config: alguns pacotes do xhtml2pdf (ex.: pycairo) podem precisar compilar.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ============================================================
# Etapa 2 (final): imagem enxuta que roda a aplicação
# ============================================================
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE: não gera arquivos .pyc
# PYTHONUNBUFFERED: logs aparecem na hora no "docker logs"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Biblioteca de runtime do cairo (sem os headers de compilação)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala as dependências já compiladas na etapa anterior
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copia o código do projeto
COPY . .

# Garante que o entrypoint tenha quebra de linha Unix (LF) e seja executável,
# mesmo se o arquivo tiver sido salvo no Windows com CRLF.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

# Usuário sem privilégios de root (boa prática de segurança)
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "registro_ponto.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
