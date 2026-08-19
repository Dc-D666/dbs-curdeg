FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
# -i 指定国内 PyPI 镜像（服务器在国内，直连 pypi.org 慢/不稳）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

# 入口脚本：先 alembic upgrade head 再启动 uvicorn（详见 详细开发方案.md §10）
CMD ["./entrypoint.sh"]
