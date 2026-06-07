from __future__ import annotations

import random
import re
from typing import Any

import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll

from bitrix_client import BitrixClient
from catalog import get_catalog
from config import get_settings
from custom_actions import find_action
from keyboards import (
    ai_result_keyboard,
    catalog_keyboard,
    category_keyboard,
    confirm_add_service_keyboard,
    main_keyboard,
    order_review_keyboard,
    portfolio_keyboard,
)
from openai_client import OpenAIAdvisor
from states import (
    AI_POST_RESULT,
    AI_WAITING_BRIEF,
    CATALOG as CATALOG_STATE,
    CATALOG_CATEGORY,
    CATALOG_CONFIRM_ADD,
    MAIN_MENU,
    ORDER_COMMENT,
    ORDER_EMAIL,
    ORDER_NAME,
    ORDER_PHONE,
    ORDER_REVIEW,
    ORDER_REVIEW_REMOVE,
    SUPPORT_DESCRIPTION,
    SUPPORT_EMAIL,
    SUPPORT_NAME,
    SUPPORT_PHONE,
)
from storage import Storage


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_ALLOWED_RE = re.compile(r"^[\d\+\-\(\)\s]{7,25}$")


class VKBot:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.vk_group_token:
            raise RuntimeError("VK_GROUP_TOKEN is empty")

        self.storage = Storage(self.settings.db_path)
        self.bitrix = BitrixClient(self.settings.bitrix_webhook_url)
        self.advisor = OpenAIAdvisor(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
        )

        self.vk_session = vk_api.VkApi(token=self.settings.vk_group_token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        cleaned = re.sub(r"[^\d+]", "", raw.strip())
        if cleaned.startswith("8") and len(cleaned) == 11:
            cleaned = "+7" + cleaned[1:]
        if cleaned.startswith("7") and len(cleaned) == 11:
            cleaned = "+" + cleaned
        return cleaned

    @staticmethod
    def _is_valid_phone(raw: str) -> bool:
        if not PHONE_ALLOWED_RE.match(raw.strip()):
            return False
        digits = re.sub(r"\D", "", raw)
        return 10 <= len(digits) <= 15

    def send_message(self, user_id: int, text: str, keyboard: str | None = None) -> None:
        self.vk.messages.send(
            user_id=user_id,
            message=text,
            random_id=random.randint(1, 2_000_000_000),
            keyboard=keyboard,
        )

    def reset_to_main(self, user_id: int, payload: dict[str, Any] | None = None) -> None:
        self.storage.upsert_user(user_id=user_id, state=MAIN_MENU, payload=payload or {})
        self.send_message(
            user_id,
            (
                f"Здравствуйте! Я помощник {self.settings.company_name}. "
                "Помогу выбрать услугу, показать портфолио и быстро оформить заявку."
            ),
            keyboard=main_keyboard(),
        )

    def start(self) -> None:
        print("VK bot started.")
        for event in self.longpoll.listen():
            if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
                continue
            user_id = event.user_id
            text = (event.text or "").strip()
            self.handle_message(user_id, text)

    def handle_message(self, user_id: int, text: str) -> None:
        lower = text.lower()
        if lower in {"/start", "start", "начать", "привет", "/menu"}:
            self.reset_to_main(user_id)
            return
        if lower in {"/cancel", "отмена"}:
            self.send_message(user_id, "Текущий сценарий отменен.")
            self.reset_to_main(user_id)
            return
        if lower in {"/help", "help"}:
            self.send_message(
                user_id,
                "Доступные разделы: Каталог, Портфолио, Помощь с выбором, Консультация/техподдержка.",
                keyboard=main_keyboard(),
            )
            return

        ctx = self.storage.get_user_context(user_id=user_id, default_state=MAIN_MENU)
        state = ctx.state
        payload = ctx.payload

        if text == "Главное меню":
            self.reset_to_main(user_id)
            return
        if text == "Каталог":
            preserved_selected = payload.get("selected_services", [])
            self.storage.upsert_user(
                user_id,
                CATALOG_STATE,
                {"selected_services": preserved_selected},
            )
            self.send_message(user_id, "Выберите категорию услуг:", keyboard=catalog_keyboard())
            return
        if text == "Портфолио":
            self.send_message(
                user_id,
                f"Посмотреть примеры работ можно здесь: {self.settings.portfolio_url}",
                keyboard=portfolio_keyboard(),
            )
            return
        if text == "Перейти в каталог":
            self.storage.upsert_user(user_id, CATALOG_STATE, payload)
            self.send_message(user_id, "Выберите категорию услуг:", keyboard=catalog_keyboard())
            return
        if text == "Помощь с выбором":
            self.storage.upsert_user(user_id, AI_WAITING_BRIEF, payload)
            self.send_message(
                user_id,
                "Опишите вашу компанию и цель. Я подберу подходящие услуги.",
                keyboard=main_keyboard(),
            )
            return
        if text == "Консультация/техподдержка":
            self.storage.upsert_user(
                user_id,
                SUPPORT_DESCRIPTION,
                {"request_type": "support"},
            )
            self.send_message(
                user_id,
                "Опишите проблему или вопрос, с которым нужна помощь.",
                keyboard=main_keyboard(),
            )
            return

        custom_action = find_action(text)
        if custom_action:
            self.send_message(user_id, custom_action["response"], keyboard=main_keyboard())
            return

        if state in {CATALOG_STATE, CATALOG_CATEGORY, CATALOG_CONFIRM_ADD}:
            self._handle_catalog(user_id, text, payload)
            return
        if state in {ORDER_REVIEW, ORDER_REVIEW_REMOVE}:
            self._handle_order_review(user_id, text, payload, state)
            return
        if state in {ORDER_NAME, ORDER_PHONE, ORDER_EMAIL, ORDER_COMMENT}:
            self._handle_order_form(user_id, text, payload, state)
            return
        if state == AI_WAITING_BRIEF:
            self._handle_ai_brief(user_id, text, payload)
            return
        if state == AI_POST_RESULT:
            self._handle_ai_post_result(user_id, text, payload)
            return
        if state in {SUPPORT_DESCRIPTION, SUPPORT_NAME, SUPPORT_PHONE, SUPPORT_EMAIL}:
            self._handle_support_form(user_id, text, payload, state)
            return

        self.send_message(
            user_id,
            "Выберите раздел в меню: каталог, портфолио, помощь с выбором или консультация.",
            keyboard=main_keyboard(),
        )

    def _handle_catalog(self, user_id: int, text: str, payload: dict[str, Any]) -> None:
        catalog = get_catalog()
        if text in catalog:
            new_payload = payload or {}
            new_payload["category"] = text
            new_payload.setdefault("selected_services", [])
            self.storage.upsert_user(user_id, CATALOG_CATEGORY, new_payload)
            self.send_message(user_id, f"Раздел: {text}. Выберите услугу:", keyboard=category_keyboard(text))
            return

        if text == "Назад в каталог":
            self.storage.upsert_user(user_id, CATALOG_STATE, payload)
            self.send_message(user_id, "Выберите категорию услуг:", keyboard=catalog_keyboard())
            return

        category = payload.get("category")
        if payload.get("pending_service") and text == "Вернуться назад":
            payload.pop("pending_service", None)
            self.storage.upsert_user(user_id, CATALOG_CATEGORY, payload)
            self.send_message(
                user_id,
                "Выберите услугу или нажмите 'Оформить заявку'.",
                keyboard=category_keyboard(category),
            )
            return

        if payload.get("pending_service") and text == "Добавить в заявку":
            service_to_add = payload.get("pending_service")
            selected = payload.setdefault("selected_services", [])
            if service_to_add and service_to_add not in selected:
                selected.append(service_to_add)
            payload.pop("pending_service", None)
            self.storage.upsert_user(user_id, CATALOG_CATEGORY, payload)
            self.send_message(
                user_id,
                "Услуга добавлена в заявку. Можете выбрать еще одну или нажать 'Оформить заявку'.",
                keyboard=category_keyboard(category),
            )
            return

        if category and category in catalog and text in catalog[category]:
            desc = catalog[category][text]
            payload["pending_service"] = text
            self.storage.upsert_user(user_id, CATALOG_CONFIRM_ADD, payload)
            self.send_message(
                user_id,
                f"{text}\n\n{desc}\n\nХотели бы добавить услугу в заявку?",
                keyboard=confirm_add_service_keyboard(),
            )
            return

        if text == "Оформить заявку":
            selected = payload.get("selected_services", [])
            if not selected:
                self.send_message(
                    user_id,
                    "Вы пока не выбрали услуги. Добавьте хотя бы одну услугу перед оформлением.",
                    keyboard=catalog_keyboard(),
                )
                return
            self.storage.upsert_user(user_id, ORDER_REVIEW, payload)
            self._show_order_review(user_id, payload)
            return

        self.send_message(user_id, "Выберите категорию или услугу с клавиатуры.", keyboard=catalog_keyboard())

    def _show_order_review(self, user_id: int, payload: dict[str, Any]) -> None:
        selected = payload.get("selected_services", [])
        lines = [f"{idx}. {name}" for idx, name in enumerate(selected, 1)]
        text = "В заявке сейчас:\n" + "\n".join(lines) + "\n\nПодтвердить заявку или удалить услугу?"
        self.send_message(user_id, text, keyboard=order_review_keyboard())

    def _handle_order_review(
        self,
        user_id: int,
        text: str,
        payload: dict[str, Any],
        state: str,
    ) -> None:
        selected = payload.get("selected_services", [])
        if not selected:
            self.storage.upsert_user(user_id, CATALOG_STATE, payload)
            self.send_message(
                user_id,
                "Список услуг пуст. Выберите услуги в каталоге.",
                keyboard=catalog_keyboard(),
            )
            return

        if state == ORDER_REVIEW:
            if text == "Подтвердить заявку":
                payload["request_type"] = "catalog"
                self.storage.upsert_user(user_id, ORDER_NAME, payload)
                self.send_message(user_id, "Оформляем заявку.\nКак вас зовут?", keyboard=main_keyboard())
                return
            if text == "Удалить услугу":
                self.storage.upsert_user(user_id, ORDER_REVIEW_REMOVE, payload)
                self.send_message(
                    user_id,
                    "Введите номер услуги для удаления (например: 2).",
                    keyboard=order_review_keyboard(),
                )
                return
            if text == "Назад в каталог":
                self.storage.upsert_user(user_id, CATALOG_STATE, payload)
                self.send_message(user_id, "Выберите категорию услуг:", keyboard=catalog_keyboard())
                return
            self._show_order_review(user_id, payload)
            return

        # ORDER_REVIEW_REMOVE
        if text == "Назад в каталог":
            self.storage.upsert_user(user_id, CATALOG_STATE, payload)
            self.send_message(user_id, "Выберите категорию услуг:", keyboard=catalog_keyboard())
            return
        if text == "Подтвердить заявку":
            self.storage.upsert_user(user_id, ORDER_REVIEW, payload)
            self._show_order_review(user_id, payload)
            return

        try:
            idx = int(text.strip()) - 1
            if idx < 0 or idx >= len(selected):
                raise ValueError
        except ValueError:
            self.send_message(
                user_id,
                "Неверный номер. Введите номер услуги из списка.",
                keyboard=order_review_keyboard(),
            )
            return

        removed = selected.pop(idx)
        payload["selected_services"] = selected
        self.storage.upsert_user(user_id, ORDER_REVIEW, payload)
        if not selected:
            self.storage.upsert_user(user_id, CATALOG_STATE, payload)
            self.send_message(
                user_id,
                f"Услуга '{removed}' удалена. Список пуст, выберите услуги заново.",
                keyboard=catalog_keyboard(),
            )
            return
        self.send_message(user_id, f"Удалено: {removed}")
        self._show_order_review(user_id, payload)

    def _handle_order_form(
        self,
        user_id: int,
        text: str,
        payload: dict[str, Any],
        state: str,
    ) -> None:
        if state == ORDER_NAME:
            payload["name"] = text
            self.storage.upsert_user(user_id, ORDER_PHONE, payload, full_name=text)
            self.send_message(user_id, "Введите номер телефона:")
            return
        if state == ORDER_PHONE:
            if not self._is_valid_phone(text):
                self.send_message(
                    user_id,
                    "Введите корректный телефон, например: +7 999 123-45-67",
                )
                return
            normalized_phone = self._normalize_phone(text)
            payload["phone"] = normalized_phone
            self.storage.upsert_user(user_id, ORDER_EMAIL, payload, phone=normalized_phone)
            self.send_message(user_id, "Введите email:")
            return
        if state == ORDER_EMAIL:
            if not EMAIL_RE.match(text):
                self.send_message(
                    user_id,
                    "Пожалуйста, введите корректный email, например: name@example.com",
                )
                return
            payload["email"] = text
            self.storage.upsert_user(user_id, ORDER_COMMENT, payload, email=text)
            self.send_message(user_id, "Добавьте комментарий (или напишите 'нет'):")
            return
        if state == ORDER_COMMENT:
            payload["comment"] = "" if text.lower() == "нет" else text
            self._submit_catalog_or_ai_request(user_id, payload)

    def _handle_ai_brief(self, user_id: int, text: str, payload: dict[str, Any]) -> None:
        advice = self.advisor.suggest(text)
        recommendations = advice.get("recommended_services", [])
        rec_block = "\n".join(f"- {item}" for item in recommendations) or "- Консультация специалиста"
        message = (
            f"Рекомендации:\n{rec_block}\n\n"
            f"Почему: {advice.get('reason', 'Уточните задачу на консультации.')}\n\n"
            f"{advice.get('message_to_client', '')}"
        )
        payload["ai_client_brief"] = text
        payload["ai_advice"] = advice
        payload["selected_services"] = recommendations
        self.storage.upsert_user(user_id, AI_POST_RESULT, payload)
        self.send_message(user_id, message, keyboard=ai_result_keyboard())

    def _handle_ai_post_result(self, user_id: int, text: str, payload: dict[str, Any]) -> None:
        if text == "Оставить заявку":
            payload["request_type"] = "ai_help"
            self.storage.upsert_user(user_id, ORDER_NAME, payload)
            self.send_message(user_id, "Хорошо, оформим заявку. Как вас зовут?", keyboard=main_keyboard())
            return
        if text == "Перейти в каталог":
            self.storage.upsert_user(user_id, CATALOG_STATE, payload)
            self.send_message(user_id, "Выберите категорию услуг:", keyboard=catalog_keyboard())
            return
        self.send_message(user_id, "Выберите действие с кнопок.", keyboard=ai_result_keyboard())

    def _handle_support_form(
        self,
        user_id: int,
        text: str,
        payload: dict[str, Any],
        state: str,
    ) -> None:
        if state == SUPPORT_DESCRIPTION:
            payload["support_description"] = text
            self.storage.upsert_user(user_id, SUPPORT_NAME, payload)
            self.send_message(user_id, "Как вас зовут?")
            return
        if state == SUPPORT_NAME:
            payload["name"] = text
            self.storage.upsert_user(user_id, SUPPORT_PHONE, payload, full_name=text)
            self.send_message(user_id, "Введите номер телефона:")
            return
        if state == SUPPORT_PHONE:
            if not self._is_valid_phone(text):
                self.send_message(
                    user_id,
                    "Введите корректный телефон, например: +7 999 123-45-67",
                )
                return
            normalized_phone = self._normalize_phone(text)
            payload["phone"] = normalized_phone
            self.storage.upsert_user(user_id, SUPPORT_EMAIL, payload, phone=normalized_phone)
            self.send_message(user_id, "Введите email:")
            return
        if state == SUPPORT_EMAIL:
            if not EMAIL_RE.match(text):
                self.send_message(
                    user_id,
                    "Пожалуйста, введите корректный email, например: name@example.com",
                )
                return
            payload["email"] = text
            self._submit_support_request(user_id, payload)

    def _submit_catalog_or_ai_request(self, user_id: int, payload: dict[str, Any]) -> None:
        req_type = payload.get("request_type", "catalog")
        selected = payload.get("selected_services", [])
        comment = payload.get("comment", "")
        details = {
            "request_type": req_type,
            "user_id": user_id,
            "name": payload.get("name", ""),
            "phone": payload.get("phone", ""),
            "email": payload.get("email", ""),
            "selected_services": selected,
            "comment": comment,
            "ai_client_brief": payload.get("ai_client_brief", ""),
            "ai_advice": payload.get("ai_advice", {}),
        }
        request_id = self.storage.create_request(
            user_id=user_id,
            request_type=req_type,
            title=f"Заявка из VK #{user_id}",
            details=details,
        )

        comments_lines = [
            f"Тип заявки: {req_type}",
            f"VK user id: {user_id}",
            f"Имя: {details['name']}",
            f"Телефон: {details['phone']}",
            f"Email: {details['email']}",
            "Выбранные услуги:",
            *[f"- {item}" for item in selected],
            f"Комментарий: {comment}",
        ]
        if req_type == "ai_help":
            comments_lines += [
                "",
                "Блок ИИ:",
                f"Запрос клиента: {details['ai_client_brief']}",
                f"Ответ ИИ: {details['ai_advice']}",
            ]

        ok, result = self.bitrix.create_lead(
            title=f"VK: {details['name']} ({req_type})",
            fields={
                "NAME": details["name"],
                "PHONE": [{"VALUE": details["phone"], "VALUE_TYPE": "WORK"}],
                "EMAIL": [{"VALUE": details["email"], "VALUE_TYPE": "WORK"}],
                "SOURCE_ID": "WEB",
            },
            comments="\n".join(comments_lines),
        )
        self.storage.set_request_status(request_id, "SENT" if ok else "FAILED")
        if ok:
            self.send_message(
                user_id,
                "Спасибо! Заявка отправлена в работу. Специалист свяжется с вами.",
                keyboard=main_keyboard(),
            )
        else:
            self.send_message(
                user_id,
                (
                    "Спасибо! Заявка сохранена, но при отправке в CRM возникла ошибка. "
                    "Мы получим ее и обработаем вручную."
                ),
                keyboard=main_keyboard(),
            )
            print(f"Bitrix send error for request {request_id}: {result}")

        self.storage.upsert_user(user_id, MAIN_MENU, {})

    def _submit_support_request(self, user_id: int, payload: dict[str, Any]) -> None:
        details = {
            "request_type": "support",
            "user_id": user_id,
            "name": payload.get("name", ""),
            "phone": payload.get("phone", ""),
            "email": payload.get("email", ""),
            "description": payload.get("support_description", ""),
        }
        request_id = self.storage.create_request(
            user_id=user_id,
            request_type="support",
            title=f"Поддержка из VK #{user_id}",
            details=details,
        )
        comments = (
            f"Тип заявки: support\n"
            f"VK user id: {user_id}\n"
            f"Имя: {details['name']}\n"
            f"Телефон: {details['phone']}\n"
            f"Email: {details['email']}\n"
            f"Описание: {details['description']}"
        )
        ok, result = self.bitrix.create_lead(
            title=f"VK Support: {details['name']}",
            fields={
                "NAME": details["name"],
                "PHONE": [{"VALUE": details["phone"], "VALUE_TYPE": "WORK"}],
                "EMAIL": [{"VALUE": details["email"], "VALUE_TYPE": "WORK"}],
                "SOURCE_ID": "WEB",
            },
            comments=comments,
        )
        self.storage.set_request_status(request_id, "SENT" if ok else "FAILED")
        if ok:
            self.send_message(
                user_id,
                "Спасибо! Обращение передано специалисту.",
                keyboard=main_keyboard(),
            )
        else:
            self.send_message(
                user_id,
                (
                    "Обращение сохранено, но сейчас недоступна отправка в CRM. "
                    "Мы обработаем вручную."
                ),
                keyboard=main_keyboard(),
            )
            print(f"Bitrix send error for support request {request_id}: {result}")

        self.storage.upsert_user(user_id, MAIN_MENU, {})


if __name__ == "__main__":
    bot = VKBot()
    bot.start()
