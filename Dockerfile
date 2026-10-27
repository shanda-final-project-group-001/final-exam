# 志愿星 · 校园志愿活动智能助手
# 运行：docker compose up --build  或  docker build -t volunteer-agent . && docker run --rm --env-file .env -p 127.0.0.1:8501:8501 volunteer-agent

FROM python:3.11-slim

# 国内网络加速；如需官方源可覆盖 --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 不把演示数据库打进镜像：每次启动时重建，保证名额、报名与周报可复现
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# 启动前先 seed，再拉起界面；容器内监听 0.0.0.0，宿主机只发布到 127.0.0.1
# （docker-compose.yml 与 README 的 -p 参数都限制为 127.0.0.1）
CMD ["sh", "-c", "python -m data.seed && exec streamlit run web.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true"]
