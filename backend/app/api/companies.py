from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import DB, ClientUser
from app.enums import CheckSource
from app.errors import ExternalUnavailable, NotFound
from app.models import Company, User
from app.schemas import CompanyLookupOut
from app.services import external
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
    db.add(company)
    db.flush()
    return company


@router.get("/companies/lookup", response_model=CompanyLookupOut, summary="Найти компанию по ИНН (автозаполнение)")
def lookup(_user: ClientUser, inn: str = Query(description="ИНН: 10 или 12 цифр", examples=["0010000017"])) -> CompanyLookupOut:
    return lookup_egrul(inn)
