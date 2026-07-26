# Build context is the REPO ROOT (see docker-compose.yaml) so the image can
# also carry /seed — that way seeding works on TrueNAS where only images exist.
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ /app/
COPY seed/ /seed/

EXPOSE 8000

# run migrations before serving; safe to re-run on every start
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
