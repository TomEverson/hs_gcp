FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY main.py ./
ENV PORT=8080
CMD [".venv/bin/functions-framework", "--target", "handle", "--port", "8080"]
