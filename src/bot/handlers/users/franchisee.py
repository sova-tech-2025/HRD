from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import check_user_permission, ensure_company_id, get_all_objects, get_user_by_id, get_user_by_tg_id
from bot.repositories.franchisee_repo import FranchiseeRepository
from bot.utils.logger import log_user_action

router = Router()


class FranchiseeObjectStates(StatesGroup):
    selecting_objects = State()


def _objects_keyboard(objects: list, selected_ids: set[int], user_id: int) -> InlineKeyboardMarkup:
    rows = []
    for obj in objects:
        mark = "✅" if obj.id in selected_ids else "⬜️"
        rows.append([InlineKeyboardButton(text=f"{mark} {obj.name}", callback_data=f"fr_obj_toggle:{obj.id}")])

    all_selected = bool(objects) and all(obj.id in selected_ids for obj in objects)
    toggle_all_text = "❎ Снять все" if all_selected else "🗂 Выбрать все доступные"
    rows.append([InlineKeyboardButton(text=toggle_all_text, callback_data="fr_obj_all")])
    rows.append([InlineKeyboardButton(text="💾 Готово", callback_data="fr_obj_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render(callback: CallbackQuery, state: FSMContext, objects: list, user_id: int) -> None:
    data = await state.get_data()
    selected_ids = set(data.get("franchisee_selected_object_ids", []))
    count = len(selected_ids)
    text = (
        "📍 <b>Объекты Франчайзи</b>\n\n"
        "Отметь один или несколько объектов работы — по ним Франчайзи видит и администрирует пользователей.\n\n"
        f"Выбрано: {count}"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=_objects_keyboard(objects, selected_ids, user_id)
    )


async def _load_objects(session: AsyncSession, state: FSMContext, tg_id: int) -> list:
    company_id = await ensure_company_id(session, state, tg_id)
    return await get_all_objects(session, company_id)


@router.callback_query(F.data.startswith("franchisee_objects:"))
async def callback_franchisee_objects(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    actor = await get_user_by_tg_id(session, callback.from_user.id)
    if not actor or not await check_user_permission(session, actor.id, "manage_users"):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    target = await get_user_by_id(session, user_id)
    if not target:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    objects = await _load_objects(session, state, callback.from_user.id)
    if not objects:
        await callback.answer("В компании нет объектов", show_alert=True)
        return

    current = await FranchiseeRepository(session).get_object_ids(user_id)
    await state.update_data(
        franchisee_target_user_id=user_id,
        franchisee_selected_object_ids=list(current),
    )
    await state.set_state(FranchiseeObjectStates.selecting_objects)
    await _render(callback, state, objects, user_id)
    await callback.answer()
    log_user_action(callback.from_user.id, callback.from_user.username, "franchisee_objects_open", {"target": user_id})


@router.callback_query(FranchiseeObjectStates.selecting_objects, F.data.startswith("fr_obj_toggle:"))
async def callback_toggle_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    object_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("franchisee_selected_object_ids", []))
    user_id = data.get("franchisee_target_user_id")

    if object_id in selected:
        selected.discard(object_id)
    else:
        selected.add(object_id)
    await state.update_data(franchisee_selected_object_ids=list(selected))

    objects = await _load_objects(session, state, callback.from_user.id)
    await _render(callback, state, objects, user_id)
    await callback.answer()


@router.callback_query(FranchiseeObjectStates.selecting_objects, F.data == "fr_obj_all")
async def callback_toggle_all(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user_id = data.get("franchisee_target_user_id")
    objects = await _load_objects(session, state, callback.from_user.id)
    object_ids = {obj.id for obj in objects}
    selected = set(data.get("franchisee_selected_object_ids", []))

    if object_ids and object_ids.issubset(selected):
        selected -= object_ids
    else:
        selected |= object_ids
    await state.update_data(franchisee_selected_object_ids=list(selected))

    await _render(callback, state, objects, user_id)
    await callback.answer()


@router.callback_query(FranchiseeObjectStates.selecting_objects, F.data == "fr_obj_done")
async def callback_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user_id = data.get("franchisee_target_user_id")
    selected = list(data.get("franchisee_selected_object_ids", []))

    if not selected:
        await callback.answer("Выбери хотя бы один объект", show_alert=True)
        return

    await FranchiseeRepository(session).set_objects(user_id, selected)
    target = await get_user_by_id(session, user_id)
    name = target.full_name if target else f"#{user_id}"

    await state.clear()
    await callback.message.edit_text(
        f"✅ Объекты Франчайзи для <b>{name}</b> сохранены: {len(selected)}.", parse_mode="HTML"
    )
    await callback.answer()
    log_user_action(
        callback.from_user.id,
        callback.from_user.username,
        "franchisee_objects_saved",
        {"target": user_id, "count": len(selected)},
    )
