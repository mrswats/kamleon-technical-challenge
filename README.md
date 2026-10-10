# Kamleon Technical Challenge

This repository contains my solution to the Kamleon Technical Challenge.

## Installation

Create a virtual Environment, install dependencies.

```console
virtualenv .venv -p pytthon 3.14
source .venv/bin/activate
pip install -r test-requirements.txt
```

### Running locally

Development server:

```console
./manage.py migrate
./manage.py runserver
```

### Running Docker locally

```console
docker compose build
docker compose up -d
```

Then, the API server is accessible on `http://localhost:8080/`

## Tests

Using pytest for Tests, and getting a coverage report in terminal.

```console
python -m pytest --cov --cov-report term-missing
```

## Formatting and Linting

Using pre-commit for linting and formatting

```console
pre-commit install
pre-commit run --all-files
```
## Documentation

API documentation is accessible with the running local server at
[http://localhost:8000/docs/](http://localhost:8000/docs/).

## Data model

The data model is as follows:

![Data model](./img/models.png)
