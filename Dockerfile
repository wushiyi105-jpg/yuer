FROM python:3.10-slim

LABEL org.opencontainers.image.source="https://github.com/wushiyi105-jpg/yuer"
LABEL org.opencontainers.image.description="育儿 · 生长与喂养参考:百分位分档、矫正月龄、接种表、喂养区间,不做诊断"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8000

CMD ["python", "-m", "yuer", "web", "--host", "0.0.0.0"]
