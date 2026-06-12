# ── CTP 行情引擎 Docker 镜像 ──────────────────────
# 构建: docker build -f ctp_engine/Dockerfile -t ctp_engine .
# 运行: docker run -d --name ctp_engine \
#         -v $(pwd)/ctp_engine/.env:/app/.env \
#         -v $(pwd)/ctp_engine/data:/app/data \
#         -v $(pwd)/ctp_engine/logs:/app/logs \
#         -p 127.0.0.1:9999:9999 \
#         ctp_engine

FROM python:3.12-slim-bookworm

WORKDIR /app

# 时区 + CTP .so 可能依赖的库
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip install --no-cache-dir \
    openctp-ctp \
    tabulate \
    python-dotenv

COPY ctp_engine/ ./

RUN mkdir -p data logs flow_md flow_td

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import socket;s=socket.socket();s.connect(('127.0.0.1',9999));s.close()" || exit 1

EXPOSE 9999

CMD ["python", "main.py"]
