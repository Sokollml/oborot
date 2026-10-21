from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DB
from app.models import Product
from app.schemas import ProductOption, ProductOut, RecommendIn, RecommendOut
from app.services.recommend import Option, recommend

router = APIRouter(tags=["Продукты"])


def _all_products(db: DB) -> list[Product]:
    return list(db.scalars(select(Product).order_by(Product.max_amount)))


@router.get("/products", response_model=list[ProductOut], summary="Список кредитных продуктов")
def list_products(db: DB) -> list[Product]:
    return _all_products(db)


def _option_out(o: Option) -> ProductOption:
    return ProductOption(
        product=ProductOut.model_validate(o.product),
        fits=o.fits,
        reason=o.reason,
        amount=o.amount,
        term_months=o.term_months,
        rate_from=o.product.base_rate,
        monthly_payment_from=o.monthly_payment,
    )


@router.post("/products/recommend", response_model=RecommendOut, summary="Подобрать продукт по цели, сумме и сроку")
def recommend_product(body: RecommendIn, db: DB) -> RecommendOut:
    best, alternatives = recommend(_all_products(db), body.purpose, body.amount, body.term_months)
    return RecommendOut(recommended=_option_out(best), alternatives=[_option_out(o) for o in alternatives])
