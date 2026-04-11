ROLE_PRIORITY = {
    "ADMIN": 6,
    "Руководитель": 5,
    "Рекрутер": 4,
    "Наставник": 3,
    "Сотрудник": 2,
    "Стажер": 1,
}


def get_primary_role(roles) -> str:
    """Возвращает имя роли с наивысшим приоритетом.

    roles — список объектов с атрибутом .name или список строк.
    """
    if not roles:
        return "Неавторизованный"
    names = [r.name if hasattr(r, "name") else r for r in roles]
    return max(names, key=lambda r: ROLE_PRIORITY.get(r, 0))
