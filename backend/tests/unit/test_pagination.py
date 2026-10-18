import pytest
from pydantic import ValidationError

from app.common.pagination import MAX_PAGE_SIZE, Page, PageParams


def test_offset_and_limit() -> None:
    params = PageParams(page=3, page_size=20)
    assert (params.offset, params.limit) == (40, 20)


@pytest.mark.parametrize(
    "kwargs", [{"page": 0}, {"page_size": 0}, {"page_size": MAX_PAGE_SIZE + 1}]
)
def test_invalid_params_rejected(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        PageParams(**kwargs)


def test_page_envelope() -> None:
    page = Page[str].build(["a", "b"], total=5, params=PageParams(page=2, page_size=2))
    assert page.model_dump() == {"items": ["a", "b"], "total": 5, "page": 2, "page_size": 2}
