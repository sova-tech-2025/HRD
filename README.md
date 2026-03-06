<p align="center"><img src="assets/images/readme_logo/photo_2026-02-23_07-41-40.jpg" alt="HRD" width="300" /></p>
<h3 align="center">Telegram-бот для управления персоналом и обучением в HoReCa</h3>
<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/Aiogram-3.x-blue?logo=telegram&logoColor=white" alt="Aiogram"></a>
  <a href="#"><img src="https://img.shields.io/badge/PostgreSQL-17-336791?logo=postgresql&logoColor=white" alt="PostgreSQL"></a>
  <a href="#"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" alt="Docker"></a>
</p>
<hr/>

HRD (Human Resource Development) — платформа для адаптации и обучения линейного персонала в кафе и ресторанах. Бот работает прямо в Telegram — без корпоративных email, без сложных HR-систем. Стажёр присоединяется по коду приглашения компании, проходит обучение и тесты, получает наставника и по итогам аттестации становится сотрудником.

- **Онбординг через Telegram** — регистрация по коду приглашения компании, мгновенный старт обучения без дополнительных приложений.
- **Тестирование** — 5 типов вопросов, настраиваемый проходной балл, попытки, перемешивание и штрафные баллы. Тесты по меню, стандартам обслуживания, охране труда.
- **Траектории обучения** — 4 уровня (траектория → этап → сессия → тест) для пошагового обучения с отслеживанием прогресса.
- **Наставничество** — назначение наставников стажёрам, контроль прогресса и управление доступом к тестам в реальном времени.
- **Аттестации** — руководители проводят аттестации и переводят стажёров в статус сотрудника.
- **База знаний** — учебные материалы в папках с разграничением доступа по группам.
- **Мультитенантность** — полная изоляция данных компаний, подписки с лимитом пользователей, trial-период.

## Quick Start

Создайте файл `.env` и запустите бота через Docker Compose:

```bash
cat > .env << EOF
BOT_TOKEN=your_telegram_bot_token
POSTGRES_DB=hrd
POSTGRES_USER=hrd_user
POSTGRES_PASSWORD=your_secure_password
ADMIN_INIT_TOKEN=your_admin_token
EOF

docker-compose up -d
```

Откройте бота в Telegram и отправьте `/start`. Используйте `ADMIN_INIT_TOKEN` для создания первой компании.

## Screenshots

<!-- Добавьте скриншоты бота -->
<table style="border-collapse: collapse; border: 1px solid black;">
  <tr>
    <td style="padding: 5px;background-color:#fff;"><img src="assets/images/screenshot_1.png" alt="HRD Screenshot 1" /></td>
    <td style="padding: 5px;background-color:#fff;"><img src="assets/images/screenshot_2.png" alt="HRD Screenshot 2" /></td>
  </tr>
  <tr>
    <td style="padding: 5px;background-color:#fff;"><img src="assets/images/screenshot_3.png" alt="HRD Screenshot 3" /></td>
    <td style="padding: 5px;background-color:#fff;"><img src="assets/images/screenshot_4.png" alt="HRD Screenshot 4" /></td>
  </tr>
</table>

## Technical Stack

- Backend: [Python 3.11+](https://www.python.org/) / [Aiogram 3.x](https://docs.aiogram.dev/)
- ORM: [SQLAlchemy 2.0+](https://www.sqlalchemy.org/) (async)
- Database: [PostgreSQL 17](https://www.postgresql.org/)
- Scheduler: [APScheduler](https://apscheduler.readthedocs.io/)
- Containerization: [Docker](https://www.docker.com/)
