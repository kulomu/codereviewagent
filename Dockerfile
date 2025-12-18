# 构建阶段
FROM ghcr.io/astral-sh/uv:bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Configure the Python directory so it is consistent
ENV UV_PYTHON_INSTALL_DIR=/python

# Only use the managed Python version
ENV UV_PYTHON_PREFERENCE=only-managed

# Install Python before the project for caching
RUN uv python install 3.13

WORKDIR /app

COPY . /app
RUN  uv sync --locked --no-dev

# 运行阶段
# Then, use a final image 
FROM ghcr.io/astral-sh/uv:bookworm-slim

ARG TY_ACCESS_KEY
ARG TY_SECRET_KEY
ARG TY_REGION
ARG TY_GITLAB_TOKEN

ENV AWS_ACCESS_KEY_ID=${TY_ACCESS_KEY}
ENV AWS_SECRET_ACCESS_KEY=${TY_SECRET_KEY}
ENV AWS_ACCESS_REGION=${TY_REGION}
ENV GITLAB_TOKEN=${TY_GITLAB_TOKEN}

# 安装 git 和 bash，并确保 /bin/sh 存在
RUN apt-get update && \
    apt-get install -y git bash && \
    ln -sf /bin/bash /bin/sh && \
    rm -rf /var/lib/apt/lists/*

# Copy the Python version
COPY --from=builder /python /python

# Copy the application from the builder
COPY --from=builder /app /app

# 设置环境变量
ENV PATH="/app/.venv/bin:$PATH" 

# 设置入口点
# ENTRYPOINT ["python", "-m", "cli", "import sys; print(sys.argv)"]
CMD ["python", "-m", "cli"]