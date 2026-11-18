# Async-Job-Processing-API

## Setup

Create a virtual environment and install the dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Pyrefly uses the project `.venv` to resolve imports. Select `.venv/bin/python`
as your editor's Python interpreter as well.

## Run

```sh
.venv/bin/uvicorn app:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API. Jobs are stored in
`jobs.db` by default. Set `DATABASE_URL` to another SQLAlchemy database URL
to use a different database.

Submit a job with `POST /jobs` and JSON such as `{"text": "hello"}`. The worker
converts the text to uppercase. Use `GET /jobs/{id}` to check its status,
`GET /jobs` to list jobs, or `GET /jobs/{id}/events` to stream status changes
as server sent events. Queued and running jobs resume when the server starts.

## Test

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```
