#! /usr/bin/env python
from __future__ import annotations

import argparse
import os
from typing import NoReturn
from typing import Sequence

import django
import redis
import rq

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kamleon.settings.local")


def _setup():
    django.setup()


def _work(queue: str, redis_url: str) -> NoReturn:
    r = redis.StrictRedis.from_url(redis_url)

    w = rq.Worker(queue, connection=r)
    w.work()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("redis_url")
    parser.add_argument("queue")
    parsed_args = parser.parse_args(argv)

    _setup()
    _work(parsed_args.queue, parsed_args.redis_url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
