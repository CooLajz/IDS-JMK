FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && useradd --uid 10001 --create-home ids \
    && mkdir /data && chown ids:ids /data
COPY api ./api
COPY LICENSE ./LICENSE
LABEL org.opencontainers.image.source="https://github.com/CooLajz/IDS-JMK" \
      org.opencontainers.image.licenses="MIT"
USER 10001:10001
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready',timeout=3)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
