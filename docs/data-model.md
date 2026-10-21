# Модель данных

Одна база PostgreSQL на оба кабинета. Таблицы описаны в
[`backend/app/models.py`](../backend/app/models.py), миграции — в `backend/migrations/versions/`
(применяются автоматически при старте `api`).

Соглашения: деньги — целые рубли (`BIGINT`), ставки — проценты годовых, все перечисления хранятся строками,
время — с часовым поясом.

```mermaid
erDiagram
    users ||--o{ companies : "владеет"
    users ||--o{ notifications : "получает"
    companies ||--o{ applications : "подаёт"
    products ||--o{ applications : "по продукту"
    applications ||--o{ status_history : "история статусов"
    applications ||--o{ check_results : "ответы ЕГРЮЛ/ФНС/БКИ"
    applications ||--o{ scorings : "оценки"
    applications ||--o{ decisions : "решения"
    applications ||--o{ document_requests : "документы"
    applications ||--o{ jobs : "задачи воркера"
    applications ||--o{ notifications : "о заявке"

    users {
        int id PK
        string email UK
        string password_hash "bcrypt"
        string role "client | analyst"
        string full_name
    }
    companies {
        int id PK
        int owner_user_id FK
        string inn "10 или 12 цифр"
        string ogrn
        string name
        string okved
        date registered_at
        string status "active | liquidating | bankrupt"
        string director
    }
    products {
        int id PK
        string code UK "EXPRESS | WORKING | INVEST"
        string name
        bigint min_amount
        bigint max_amount
        int min_term
        int max_term
        bool needs_collateral
        float base_rate
    }
    applications {
        int id PK
        int company_id FK
        int product_id FK
        string purpose "stock_salary | equipment | urgent"
        bigint amount
        int term_months
        bigint revenue_12m
        bigint revenue_prev_year
        bigint monthly_debt_payments
        int employees
        text collateral_description
        bool bki_consent
        string status "меняется только через transition()"
        string signing_code "симуляция подписи"
        string idempotency_key UK
        timestamptz created_at
        timestamptz updated_at
    }
    status_history {
        int id PK
        int application_id FK
        string from_status
        string to_status
        string actor_type "client | analyst | system"
        int actor_id FK
        text comment
        timestamptz created_at
    }
    check_results {
        int id PK
        int application_id FK
        string source "egrul | fns | bki"
        bool ok
        json payload "ответ сервиса или ошибка"
        timestamptz fetched_at
    }
    scorings {
        int id PK
        int application_id FK
        int total_score "0–100"
        string risk_class "A | B | C | D"
        json factors "вклад каждого фактора"
        string model_version
    }
    decisions {
        int id PK
        int application_id FK
        string type "approve | counter | info | reject"
        bigint amount
        int term
        float rate
        bigint monthly_payment
        json reasons "2–3 причины для клиента"
        json advice "советы клиенту"
        string made_by "auto | analyst"
        int analyst_id FK
    }
    document_requests {
        int id PK
        int application_id FK
        string doc_type "bank_statement | financial_report | ..."
        string status "requested | uploaded"
        string file_path "в docker volume"
        string file_name
    }
    notifications {
        int id PK
        int user_id FK
        int application_id FK
        text text
        timestamptz read_at
        timestamptz created_at
    }
    jobs {
        int id PK
        string type "process_application"
        int application_id FK
        string status "pending | running | done | failed"
        int attempts
        timestamptz run_after "для running — срок аренды"
        text last_error
    }
```

## Что добавлено к исходной схеме и зачем

| Поле | Зачем |
|---|---|
| `products.description` | короткое описание продукта для экрана подбора |
| `applications.bki_consent` | галочка согласия на запрос кредитной истории (без неё заявку не отправить) |
| `applications.signing_code` | код подписания — симуляция, показывается клиенту на экране |
| `decisions.advice` | советы клиенту хранятся отдельно от причин решения |
| `document_requests.file_name` | исходное имя файла, чтобы специалист видел, что открывает |
| `created_at` в нескольких таблицах | время этапов на ленте и сортировка очереди |

## Очередь задач

`jobs` — это и есть очередь, отдельный брокер не нужен. Воркер берёт задачу так:

```sql
SELECT ... FROM jobs
WHERE (status = 'pending' OR status = 'running') AND run_after <= now()
ORDER BY id LIMIT 1
FOR UPDATE SKIP LOCKED;
```

Взяв задачу, воркер ставит `status = 'running'` и `run_after = now() + 60 с` («аренда»).
Если он упал, через 60 секунд задачу подхватит следующий запуск. Заявка и её задача создаются
в одной транзакции при отправке — потерять задачу нельзя.
