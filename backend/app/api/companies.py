from datetime import UTC, datetime

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import DB, ClientUser
from app.enums import CheckSource
from app.errors import ExternalUnavailable, NotFound, ValidationFailed
from app.models import Company, Product, User
from app.schemas import CompanyLookupOut, MyCompanyOut, PotentialOut, PotentialRequest
from app.services import external, potential
from app.services.inn import validate_inn

router = APIRouter(tags=["Компании"])


def lookup_egrul(inn: str) -> CompanyLookupOut:
    inn = validate_inn(inn)
    try:
        data = external.fetch(CheckSource.EGRUL, inn)
    except external.CompanyNotFoundInRegistry:
        raise NotFound("Компания с таким ИНН не найдена в реестре. Проверьте номер") from None
    except external.ExternalServiceError:
        raise ExternalUnavailable("Реестр компаний сейчас не отвечает. Попробуйте через минуту") from None
    return CompanyLookupOut.model_validate(data)


def get_or_create_company(db: Session, user: User, inn: str) -> Company:
    """Компания пользователя по ИНН. Если её ещё нет — создаём по данным реестра."""
    inn = validate_inn(inn)
    company = db.scalar(select(Company).where(Company.owner_user_id == user.id, Company.inn == inn))
    if company:
        return company
    info = lookup_egrul(inn)
    company = Company(
        owner_user_id=user.id,
        inn=info.inn,
        ogrn=info.ogrn,
        name=info.name,
        okved=info.okved,
        registered_at=info.registered_at,
        status=info.status,
        director=info.director,
    )
    # Два одновременных запроса с одним ИНН: второй упрётся в уникальность (владелец, ИНН).
    # Savepoint откатывает только эту вставку — берём компанию, которую успел создать первый.
    try:
        with db.begin_nested():
            db.add(company)
    except IntegrityError:
        company = db.scalar(select(Company).where(Company.owner_user_id == user.id, Company.inn == inn))
    return company


@router.get("/companies/lookup", response_model=CompanyLookupOut, summary="Найти компанию по ИНН (автозаполнение)")
def lookup(_user: ClientUser, inn: str = Query(description="ИНН: 10 или 12 цифр", examples=["0010000017"])) -> CompanyLookupOut:
    return lookup_egrul(inn)


def _company_out(c: Company) -> MyCompanyOut:
    pot = PotentialOut(**c.potential, calculated_at=c.potential_at) if c.potential else None
    return MyCompanyOut(id=c.id, inn=c.inn, name=c.name, status=c.status, potential=pot)


@router.get("/companies", response_model=list[MyCompanyOut], summary="Мои компании и предодобренные лимиты")
def my_companies(db: DB, user: ClientUser) -> list[MyCompanyOut]:
    companies = db.scalars(select(Company).where(Company.owner_user_id == user.id).order_by(Company.name)).all()
    return [_company_out(c) for c in companies]


@router.post(
    "/companies/{company_id}/potential",
    response_model=MyCompanyOut,
    summary="Рассчитать предодобренный лимит (без документов)",
)
def calculate_potential(company_id: int, body: PotentialRequest, db: DB, user: ClientUser) -> MyCompanyOut:
    if not body.consent:
        raise ValidationFailed("Чтобы рассчитать лимит, нужно согласие на запрос кредитной истории")
    company = db.get(Company, company_id)
    if company is None or company.owner_user_id != user.id:
        raise NotFound("Компания не найдена")
    company.potential = potential.calculate(company, list(db.scalars(select(Product))))
    company.potential_at = datetime.now(UTC)
    db.commit()
    return _company_out(company)
