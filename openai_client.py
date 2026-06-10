from __future__ import annotations

import json

from openai import OpenAI

from catalog import get_all_services, get_catalog, get_service_description


class OpenAIAdvisor:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = model

    def suggest(self, user_brief: str) -> dict[str, object]:
        if not self.client:
            return {
                "recommended_services": [],
                "reason": "Интеграция OpenAI пока не настроена.",
                "message_to_client": (
                    "Сейчас я не могу автоматически подобрать решение. "
                    "Перейдите в каталог или оставьте заявку на консультацию."
                ),
            }

        allowed_services = get_all_services()
        services = sorted(allowed_services)
        service_context = self._build_service_context()
        system_prompt = (
            "Ты консультант по услугам digital-агентства Interinc. "
            "Interinc помогает бизнесу с цифровой трансформацией маркетинга и продаж: "
            "внедряет CRM и Битрикс24, автоматизирует бизнес-процессы, создает сайты, "
            "интернет-магазины и web-сервисы, настраивает рекламу, продвигает сайты, "
            "проектирует автоворонки, чат-боты, рассылки, аналитику и работает с репутацией. "
            "Твоя задача - подобрать клиенту наиболее подходящие услуги из каталога. "
            "Рекомендовать можно только услуги из allowed_services, строго теми же названиями. "
            "Нельзя придумывать новые услуги, цены, сроки, гарантии результата, скидки, "
            "юридические обещания, технические возможности или статус работ, которых нет в каталоге. "
            "Не говори, что Interinc точно выведет сайт в топ, гарантированно снизит стоимость заявки "
            "или даст конкретный рост продаж. Формулируй аккуратно: поможет, подойдет, стоит рассмотреть. "
            "Если информации от клиента мало, выбери 1-2 наиболее вероятные услуги и предложи консультацию. "
            "Если запрос не относится к услугам Interinc, не подбирай лишнего и предложи консультацию специалиста. "
            "Причина выбора должна быть конкретной: связать проблему клиента с выбранными услугами. "
            "Сообщение клиенту должно быть коротким, деловым и без markdown. "
            "Output strict JSON with fields: "
            "recommended_services (list[str], max 3), reason (str), message_to_client (str)."
        )
        user_prompt = (
            f"Allowed services: {services}\n"
            f"Service catalog with descriptions: {service_context}\n"
            f"Client request: {user_brief}\n"
            "Return answer in Russian."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
            return self._normalize_result(parsed)
        except Exception as first_exc:
            print(f"[OpenAIAdvisor] primary request failed: {type(first_exc).__name__}: {first_exc}")
            try:
                # Fallback path: no strict response_format, still ask for JSON-only answer.
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": user_prompt + "\nReturn only JSON. No markdown, no comments.",
                        },
                    ],
                    temperature=0.2,
                )
                content = response.choices[0].message.content or "{}"
                parsed = json.loads(content)
                return self._normalize_result(parsed)
            except Exception as second_exc:
                print(f"[OpenAIAdvisor] fallback request failed: {type(second_exc).__name__}: {second_exc}")
                return {
                    "recommended_services": [],
                    "reason": "Сервис подбора временно недоступен.",
                    "message_to_client": (
                        "Сейчас автоматический подбор недоступен. "
                        "Вы можете перейти в каталог или оставить заявку на консультацию."
                    ),
                }

    @staticmethod
    def _build_service_context() -> dict[str, dict[str, str]]:
        catalog = get_catalog()
        return {
            category: {
                service_name: get_service_description(category, service_name)
                for service_name in services
            }
            for category, services in catalog.items()
            if services
        }

    @staticmethod
    def _normalize_result(parsed: dict[str, object]) -> dict[str, object]:
        rec = parsed.get("recommended_services", [])
        allowed_services = get_all_services()
        parsed["recommended_services"] = [
            service for service in rec if service in allowed_services
        ][:3]
        parsed["reason"] = str(parsed.get("reason", "")).strip()
        parsed["message_to_client"] = str(parsed.get("message_to_client", "")).strip()
        return parsed

    def answer_support_question(
        self,
        question: str,
        article: dict[str, object],
    ) -> dict[str, str]:
        title = str(article.get("title", ""))
        url = str(article.get("url", ""))
        summary = str(article.get("summary", ""))

        fallback = {
            "answer": (
                f"Нашел подходящую статью: {title}.\n\n"
                f"{summary}\n\n"
                f"Подробнее: {url}"
            ),
            "source_title": title,
            "source_url": url,
            "mode": "fallback",
        }

        if not self.client:
            return fallback

        system_prompt = (
            "Ты первая линия поддержки по Битрикс24. "
            "Отвечай только на основе переданной статьи. "
            "Не выдумывай факты, цены, тарифные ограничения и точные пути, если их нет в статье. "
            "Ответ должен быть кратким, понятным и на русском языке. "
            "Если информации недостаточно, скажи, что лучше передать вопрос специалисту. "
            "Верни строгий JSON с полем answer."
        )
        user_prompt = (
            f"Вопрос клиента: {question}\n\n"
            f"Статья: {title}\n"
            f"Краткое содержание статьи: {summary}\n"
            f"Ссылка: {url}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
            answer = str(parsed.get("answer", "")).strip()
            if not answer:
                return fallback
            return {
                "answer": f"{answer}\n\nПодробнее: {url}",
                "source_title": title,
                "source_url": url,
                "mode": "ai",
            }
        except Exception as exc:
            print(f"[OpenAIAdvisor] support answer failed: {type(exc).__name__}: {exc}")
            return fallback
