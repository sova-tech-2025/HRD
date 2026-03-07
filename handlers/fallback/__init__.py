from aiogram import Router

from handlers.fallback import company, grouped, knowledge, registration, tests, training, universal
from utils.messages.fallback import send_fallback_message, send_use_buttons_message

router = Router()

# Порядок критичен: уникальные -> grouped -> universal
router.include_router(registration.router)
router.include_router(tests.router)
router.include_router(training.router)
router.include_router(knowledge.router)
router.include_router(company.router)
router.include_router(grouped.router)
router.include_router(universal.router)  # ПОСЛЕДНИЙ — universal fallback
