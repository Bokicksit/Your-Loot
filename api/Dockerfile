# Build context is the REPO ROOT (see docker-compose.yaml) so the image can
# also carry /seed — that way seeding works on TrueNAS where only images exist.
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ /app/
COPY seed/ /seed/
COPY VERSION /app/VERSION
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# migrations + optional first-run seed + server; safe to re-run on every start
CMD ["/app/entrypoint.sh"]
