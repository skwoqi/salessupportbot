from __future__ import annotations

from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from catalog import get_catalog
from custom_actions import get_actions


def main_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Каталог", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Портфолио", color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button("Помощь с выбором", color=VkKeyboardColor.POSITIVE)
    kb.add_button("Консультация/техподдержка", color=VkKeyboardColor.NEGATIVE)
    actions = get_actions()
    for index, action in enumerate(actions):
        kb.add_line()
        kb.add_button(action["title"], color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def catalog_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    catalog = get_catalog()
    for idx, category in enumerate(catalog.keys()):
        if idx:
            kb.add_line()
        kb.add_button(category, color=VkKeyboardColor.PRIMARY)
    if catalog:
        kb.add_line()
    kb.add_button("Главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def category_keyboard(category_name: str) -> str:
    kb = VkKeyboard(one_time=False)
    catalog = get_catalog()
    services = catalog.get(category_name, {})
    for idx, service in enumerate(services.keys()):
        if idx:
            kb.add_line()
        kb.add_button(service, color=VkKeyboardColor.PRIMARY)
    if services:
        kb.add_line()
    kb.add_button("Оформить заявку", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("Назад в каталог", color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button("Главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def confirm_add_service_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Добавить в заявку", color=VkKeyboardColor.POSITIVE)
    kb.add_button("Вернуться назад", color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button("Главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def order_review_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Подтвердить заявку", color=VkKeyboardColor.POSITIVE)
    kb.add_button("Удалить услугу", color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    kb.add_button("Назад в каталог", color=VkKeyboardColor.SECONDARY)
    kb.add_button("Главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()
 

def portfolio_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Перейти в каталог", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def ai_result_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Оставить заявку", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("Перейти в каталог", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def support_ai_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Помогло", color=VkKeyboardColor.POSITIVE)
    kb.add_button("Оставить заявку специалисту", color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    kb.add_button("Задать еще вопрос", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()
