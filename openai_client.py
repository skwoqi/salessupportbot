from __future__ import annotations

import json

from openai import OpenAI

from catalog import get_all_services


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
        system_prompt = (
            "You are a sales assistant for a digital agency. "
            "Recommend only services from the provided allowed list. "
            "Do not invent services, prices, deadlines, or guarantees. "
            "Do not provide legal, medical, or financial advice. "
            "If the request is unclear, recommend a human consultation. "
            "Output strict JSON with fields: "
            "recommended_services (list[str], max 3), reason (str), message_to_client (str)."
        )
        user_prompt = (
            f"Allowed services: {services}\n"
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
