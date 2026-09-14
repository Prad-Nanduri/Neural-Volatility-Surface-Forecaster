FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . fastapi uvicorn

COPY services/api/main.py ./
COPY tests/fixtures/btc_chain_demo.json ./demo_fixture.json
ENV VOLTERRA_DEMO_FIXTURE=/app/demo_fixture.json

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
