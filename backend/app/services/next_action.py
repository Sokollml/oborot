"""Блок «Что дальше» для клиента.

На каждом статусе клиент должен получить ответ на три вопроса:
что сейчас происходит (title + description), сколько ждать (wait_text)
и нужно ли что-то от него (action_required + code — какой экран показать).
"""

from dataclasses import dataclass

from app.enums import AppStatus, DecisionType

S = AppStatus


@dataclass
class NextAction:
    code: str  # fill_draft | wait | upload_documents | review_offer | sign | done | rejected | cancelled
    title: str
    description: str
    wait_text: str | None
    action_required: bool


def next_action(status: str, decision_type: str | None = None) -> NextAction:
    match AppStatus(status):
        case S.DRAFT:
            return NextAction(
                "fill_draft",
                "Заполните и отправьте заявку",
                "Черновик сохранён — можно продолжить с того же места.",
                None,
                True,
            )
        case S.SUBMITTED | S.CHECKING:
            return NextAction(
                "wait",
                "Проверяем данные компании",
                "Сверяем сведения о компании в реестре, налоговой и кредитной истории. От вас ничего не нужно.",
                "1–2 минуты",
                False,
            )
        case S.SCORING:
            return NextAction(
                "wait",
                "Оцениваем заявку",
                "Считаем, какую сумму и на каких условиях можем предложить. От вас ничего не нужно.",
                "меньше минуты",
                False,
            )
        case S.MANUAL_REVIEW:
            return NextAction(
                "wait",
                "Заявку смотрит специалист",
                "Специалист проверит данные и примет решение. Если понадобятся документы — мы попросим здесь.",
                "обычно до одного рабочего дня",
                False,
            )
        case S.INFO_REQUESTED:
            return NextAction(
                "upload_documents",
                "Загрузите документы",
                "Чтобы продолжить рассмотрение, нужны документы из списка ниже. После загрузки проверка продолжится сама.",
                None,
                True,
            )
        case S.OFFER:
            counter = decision_type == DecisionType.COUNTER
            return NextAction(
                "review_offer",
                "Мы можем предложить другие условия" if counter else "Заявка одобрена — посмотрите условия",
                (
                    "Всю сумму сейчас одобрить не можем, но готовы выдать меньшую. Сравните и решите."
                    if counter
                    else "Проверьте сумму, срок и платёж. Если всё подходит — примите предложение."
                ),
                None,
                True,
            )
        case S.SIGNING:
            return NextAction(
                "sign",
                "Подпишите договор кодом",
                "Введите код подтверждения — это заменяет подпись на бумаге.",
                None,
                True,
            )
        case S.ISSUED:
            return NextAction(
                "done",
                "Деньги зачислены",
                "Деньги на расчётном счёте компании. Платёж списывается раз в месяц в одну и ту же дату.",
                None,
                False,
            )
        case S.REJECTED:
            return NextAction(
                "rejected",
                "Сейчас не можем одобрить заявку",
                "Ниже — причины и что можно сделать. Можно подать заявку заново с изменёнными условиями.",
                None,
                False,
            )
        case S.CANCELLED:
            return NextAction("cancelled", "Заявка отменена", "Если передумаете — создайте новую заявку.", None, False)
