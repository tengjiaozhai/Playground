from __future__ import annotations

from datetime import datetime, timezone

from .models import FundIdentity, PortfolioPosition


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_funds() -> list[FundIdentity]:
    return [
        FundIdentity(fund_code="", fund_name="华宝石油天然气", aliases=["华宝油气"], pending_code_binding=True),
        FundIdentity(fund_code="", fund_name="标普港股低波红利", aliases=["港股低波红利"], pending_code_binding=True),
    ]


def default_portfolio() -> list[PortfolioPosition]:
    now = utc_now()
    return [
        PortfolioPosition(fund_code="", fund_name="华宝石油天然气", amount=0.0, cost=0.0, updated_at=now, pending_code_binding=True),
        PortfolioPosition(fund_code="", fund_name="标普港股低波红利", amount=0.0, cost=0.0, updated_at=now, pending_code_binding=True),
    ]
