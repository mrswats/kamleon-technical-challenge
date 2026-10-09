import redis
import rq
from django.conf import settings

r = redis.Redis.from_url(settings.REDIS_URL)


default = rq.Queue("default", connection=r)
