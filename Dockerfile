FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/

COPY requirements.txt /app/
RUN pip install -r requirements.txt

# The tree inside the image mirrors the repository (/app/src, /app/data) so the
# paths config.py resolves are identical in the container and on a dev machine —
# the locale catalog and the SQLite file are found either way.
COPY ./src /app/src
CMD ["python","src/bot.py"]