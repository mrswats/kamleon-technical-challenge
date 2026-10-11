from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi import Query
from pydantic import BaseModel


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=100, description="Page size.")] = 10,
    offset: Annotated[int, Query(ge=0, description="Number of items to skip.")] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(get_pagination)]


class Page[T](BaseModel):
    count: int
    limit: int
    offset: int
    results: list[T]
