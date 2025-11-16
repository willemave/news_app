import pytest

from app.services.scraper_configs import (
    CreateUserScraperConfig,
    create_user_scraper_config,
    list_user_scraper_configs,
)


def test_create_and_list_config(db_session):
    payload = CreateUserScraperConfig(
        scraper_type="substack",
        display_name="My Feed",
        config={"feed_url": "https://example.com/feed"},
        is_active=True,
    )
    created = create_user_scraper_config(db_session, user_id=1, data=payload)
    assert created.feed_url == "https://example.com/feed"

    configs = list_user_scraper_configs(db_session, user_id=1)
    assert len(configs) == 1
    assert configs[0].scraper_type == "substack"


def test_uniqueness_enforced(db_session):
    payload = CreateUserScraperConfig(
        scraper_type="substack",
        display_name="My Feed",
        config={"feed_url": "https://example.com/feed"},
        is_active=True,
    )
    create_user_scraper_config(db_session, user_id=1, data=payload)

    with pytest.raises(ValueError):
        create_user_scraper_config(db_session, user_id=1, data=payload)
