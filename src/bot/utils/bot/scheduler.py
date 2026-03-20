from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, select, update

from bot.database.db import async_session, get_company_recruiters
from bot.database.models import Company
from bot.utils.logger import logger
from bot.utils.timezone import MOSCOW_TZ, moscow_now

# Глобальная переменная для бота
bot = None


async def check_expired_subscriptions():
    """Проверка и деактивация истекших подписок (ежедневно в 00:00 МСК)"""
    logger.info("=== Starting subscription expiration check ===")

    try:
        async with async_session() as session:
            now_moscow = moscow_now()

            # Получаем компании с истекшими подписками
            result = await session.execute(
                select(Company).where(
                    and_(Company.subscribe == True, Company.finish_date <= now_moscow, Company.is_active == True)
                )
            )
            expired_companies = result.scalars().all()

            logger.info(f"Found {len(expired_companies)} companies with expired subscriptions")

            for company in expired_companies:
                logger.info(f"Deactivating subscription for company: {company.name} (ID: {company.id})")

                # Деактивируем подписку (используем явное обновление через update() для надежности в асинхронном контексте)
                # Если это trial подписка, устанавливаем trial=False
                update_values = {"subscribe": False}
                if company.trial == True:
                    update_values["trial"] = False
                    logger.info(f"Trial subscription expired for company: {company.name} (ID: {company.id})")

                await session.execute(update(Company).where(Company.id == company.id).values(**update_values))

                # Уведомляем Рекрутеров компании
                try:
                    recruiters = await get_company_recruiters(session, company.id, company_id=company.id)
                    logger.info(f"Notifying {len(recruiters)} recruiters of company {company.id}")

                    for recruiter in recruiters:
                        try:
                            if bot:
                                await bot.send_message(
                                    recruiter.tg_id,
                                    f"❌ <b>Подписка компании истекла!</b>\n\n"
                                    f"Компания: {company.name}\n"
                                    f"Дата окончания: {company.finish_date.strftime('%d.%m.%Y')}\n\n"
                                    f"Для продления подписки свяжитесь с оператором.\n"
                                    f"Все пользователи компании временно потеряли доступ к боту.",
                                    parse_mode="HTML",
                                )
                                logger.info(f"Sent notification to recruiter {recruiter.tg_id}")
                        except Exception as e:
                            logger.error(f"Failed to notify recruiter {recruiter.tg_id}: {e}")
                except Exception as e:
                    logger.error(f"Failed to get recruiters for company {company.id}: {e}")

            await session.commit()
            logger.info(f"=== Subscription check completed. Deactivated: {len(expired_companies)} companies ===")

    except Exception as e:
        logger.error(f"Error in check_expired_subscriptions: {e}", exc_info=True)


async def notify_subscription_expiring():
    """Уведомления о приближающемся окончании подписки (ежедневно в 10:00 МСК)"""
    logger.info("=== Starting subscription expiration warnings ===")

    try:
        async with async_session() as session:
            now = moscow_now()
            warning_periods = [3, 7, 14]  # дни до окончания

            total_notifications = 0

            for days in warning_periods:
                target_date = now + timedelta(days=days)
                # Диапазон: от target_date до target_date + 1 день
                date_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                date_end = date_start + timedelta(days=1)

                result = await session.execute(
                    select(Company).where(
                        and_(
                            Company.subscribe == True,
                            Company.is_active == True,
                            Company.finish_date >= date_start,
                            Company.finish_date < date_end,
                        )
                    )
                )
                companies = result.scalars().all()

                logger.info(f"Found {len(companies)} companies expiring in {days} days")

                for company in companies:
                    try:
                        recruiters = await get_company_recruiters(session, company.id, company_id=company.id)

                        for recruiter in recruiters:
                            try:
                                if bot:
                                    await bot.send_message(
                                        recruiter.tg_id,
                                        f"⚠️ <b>Подписка компании заканчивается!</b>\n\n"
                                        f"Компания: {company.name}\n"
                                        f"Осталось дней: {days}\n"
                                        f"Дата окончания: {company.finish_date.strftime('%d.%m.%Y')}\n\n"
                                        f"Свяжитесь с оператором для продления подписки.",
                                        parse_mode="HTML",
                                    )
                                    total_notifications += 1
                            except Exception as e:
                                logger.error(f"Failed to notify recruiter {recruiter.tg_id}: {e}")
                    except Exception as e:
                        logger.error(f"Failed to process company {company.id}: {e}")

            logger.info(f"=== Expiration warnings completed. Sent {total_notifications} notifications ===")

    except Exception as e:
        logger.error(f"Error in notify_subscription_expiring: {e}", exc_info=True)


def start_scheduler(bot_instance):
    """Запуск планировщика задач

    Args:
        bot_instance: Экземпляр бота для отправки уведомлений
    """
    global bot
    bot = bot_instance

    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    # Проверка истечения подписок - ежедневно в 00:00 МСК
    scheduler.add_job(
        check_expired_subscriptions, "cron", hour=0, minute=0, id="check_expired_subscriptions", replace_existing=True
    )
    logger.info("Scheduled job: check_expired_subscriptions (daily at 00:00 МСК)")

    # Уведомления о приближении окончания - ежедневно в 10:00 МСК
    scheduler.add_job(
        notify_subscription_expiring,
        "cron",
        hour=10,
        minute=0,
        id="notify_subscription_expiring",
        replace_existing=True,
    )
    logger.info("Scheduled job: notify_subscription_expiring (daily at 10:00 МСК)")

    scheduler.start()
    logger.info("📅 Scheduler started successfully")

    return scheduler
