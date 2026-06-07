from __future__ import annotations

import html
import os
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from catalog import UPLOAD_DIR, get_catalog, get_service_description, get_service_photo, make_service, save_catalog
from custom_actions import get_actions, save_actions

load_dotenv()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Interinc VK Bot Admin")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    if credentials.username != username or credentials.password != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )


async def read_form(request: Request) -> dict[str, str]:
    form = await request.form()
    return {
        key: str(value).strip()
        for key, value in form.items()
        if not hasattr(value, "filename")
    }


async def save_uploaded_photo(request: Request, current_photo: str = "") -> str:
    form = await request.form()
    photo = form.get("photo")
    if not photo or not getattr(photo, "filename", ""):
        return current_photo

    filename = Path(photo.filename).name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return current_photo

    target = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    with target.open("wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)
    return str(target)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def delete_photo_file(photo_path: str) -> None:
    if not photo_path:
        return
    try:
        path = Path(photo_path)
        upload_root = UPLOAD_DIR.resolve()
        resolved = path.resolve()
        if resolved.is_file() and upload_root in resolved.parents:
            resolved.unlink()
    except OSError:
        pass


def redirect_home() -> RedirectResponse:
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def index() -> str:
    catalog = get_catalog()
    actions = get_actions()
    category_options = "\n".join(
        f'<option value="{esc(name)}">{esc(name)}</option>' for name in catalog
    )
    categories_html = []

    for category_name, services in catalog.items():
        services_html = []
        for service_name, service_data in services.items():
            description = get_service_description(service_data)
            photo = get_service_photo(service_data)
            if photo:
                photo_html = f"""
                    <p class="muted">Фото: <a href="/uploads/{esc(Path(photo).name)}" target="_blank">{esc(Path(photo).name)}</a></p>
                    <form method="post" action="/service/photo/delete" onsubmit="return confirm('Удалить фото услуги?')">
                      <input type="hidden" name="category" value="{esc(category_name)}">
                      <input type="hidden" name="name" value="{esc(service_name)}">
                      <button class="danger" type="submit">Удалить фото</button>
                    </form>
                """
            else:
                photo_html = '<p class="muted">Фото не добавлено.</p>'
            services_html.append(
                f"""
                <article class="service">
                  <form method="post" action="/service/update" class="stack" enctype="multipart/form-data">
                    <input type="hidden" name="category" value="{esc(category_name)}">
                    <input type="hidden" name="old_name" value="{esc(service_name)}">
                    <label>Название услуги
                      <input name="name" value="{esc(service_name)}" required>
                    </label>
                    <label>Описание
                      <textarea name="description" rows="4" required>{esc(description)}</textarea>
                    </label>
                    {photo_html}
                    <label>Фото услуги
                      <input name="photo" type="file" accept="image/*">
                    </label>
                    <button type="submit">Сохранить услугу</button>
                  </form>
                  <form method="post" action="/service/delete" onsubmit="return confirm('Удалить услугу?')">
                    <input type="hidden" name="category" value="{esc(category_name)}">
                    <input type="hidden" name="name" value="{esc(service_name)}">
                    <button class="danger" type="submit">Удалить</button>
                  </form>
                </article>
                """
            )

        categories_html.append(
            f"""
            <section class="panel">
              <div class="panel-head">
                <h2>{esc(category_name)}</h2>
                <form method="post" action="/category/delete" onsubmit="return confirm('Удалить категорию со всеми услугами?')">
                  <input type="hidden" name="category" value="{esc(category_name)}">
                  <button class="danger" type="submit">Удалить категорию</button>
                </form>
              </div>
              {''.join(services_html) or '<p class="muted">В категории пока нет услуг.</p>'}
            </section>
            """
        )

    actions_html = []
    for index, action in enumerate(actions):
        actions_html.append(
            f"""
            <article class="service">
              <form method="post" action="/action/update" class="stack">
                <input type="hidden" name="index" value="{index}">
                <label>Название кнопки
                  <input name="title" value="{esc(action['title'])}" required>
                </label>
                <label>Ответ бота
                  <textarea name="response" rows="4" required>{esc(action['response'])}</textarea>
                </label>
                <button type="submit">Сохранить функцию</button>
              </form>
              <form method="post" action="/action/delete" onsubmit="return confirm('Удалить функцию?')">
                <input type="hidden" name="index" value="{index}">
                <button class="danger" type="submit">Удалить</button>
              </form>
            </article>
            """
        )

    return f"""
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Админ-панель VK-бота Interinc</title>
      <style>
        body {{ font-family: Segoe UI, sans-serif; margin: 0; background: #f4f6f8; color: #17202a; }}
        header {{ background: #0f172a; color: #fff; padding: 24px 32px; }}
        main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
        h1, h2, h3 {{ margin: 0; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .panel {{ background: #fff; border: 1px solid #d9e0e7; border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
        .panel-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 14px; }}
        .service {{ border-top: 1px solid #edf1f5; padding-top: 14px; margin-top: 14px; }}
        .stack {{ display: grid; gap: 10px; }}
        .row {{ display: flex; gap: 10px; align-items: center; margin-top: 10px; }}
        label {{ display: grid; gap: 6px; font-size: 14px; color: #344054; }}
        input, select, textarea {{ font: inherit; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; background: #fff; }}
        textarea {{ resize: vertical; }}
        button {{ border: 0; border-radius: 6px; background: #2563eb; color: #fff; padding: 10px 14px; cursor: pointer; }}
        button.danger {{ background: #dc2626; }}
        .muted {{ color: #667085; }}
        @media (max-width: 820px) {{ .grid {{ grid-template-columns: 1fr; }} .panel-head {{ align-items: flex-start; flex-direction: column; }} }}
      </style>
    </head>
    <body>
      <header>
        <h1>Админ-панель VK-бота Interinc</h1>
        <p>Каталог и простые функции главного меню</p>
      </header>
      <main>
        <div class="grid">
          <section class="panel">
            <h2>Добавить категорию</h2>
            <form method="post" action="/category/add" class="stack">
              <label>Название категории
                <input name="category" placeholder="Например: Маркетинг" required>
              </label>
              <button type="submit">Добавить категорию</button>
            </form>
          </section>

          <section class="panel">
            <h2>Добавить услугу</h2>
            <form method="post" action="/service/add" class="stack" enctype="multipart/form-data">
              <label>Категория
                <select name="category" required>{category_options}</select>
              </label>
              <label>Название услуги
                <input name="name" required>
              </label>
              <label>Описание
                <textarea name="description" rows="5" required></textarea>
              </label>
              <label>Фото услуги
                <input name="photo" type="file" accept="image/*">
              </label>
              <button type="submit">Добавить услугу</button>
            </form>
          </section>
        </div>

        <section class="panel">
          <h2>Добавить функцию</h2>
          <p class="muted">Функция появится отдельной кнопкой в главном меню и отправит заданный текст.</p>
          <form method="post" action="/action/add" class="stack">
            <label>Название кнопки
              <input name="title" placeholder="Например: Акции" required>
            </label>
            <label>Ответ бота
              <textarea name="response" rows="4" placeholder="Текст, который бот отправит пользователю" required></textarea>
            </label>
            <button type="submit">Добавить функцию</button>
          </form>
        </section>

        {''.join(categories_html)}

        <section class="panel">
          <h2>Функции главного меню</h2>
          {''.join(actions_html) or '<p class="muted">Дополнительных функций пока нет.</p>'}
        </section>
      </main>
    </body>
    </html>
    """


@app.post("/category/add", dependencies=[Depends(require_admin)])
async def add_category(request: Request) -> RedirectResponse:
    form = await read_form(request)
    category = form.get("category", "")
    if category:
        catalog = get_catalog()
        catalog.setdefault(category, {})
        save_catalog(catalog)
    return redirect_home()


@app.post("/category/delete", dependencies=[Depends(require_admin)])
async def delete_category(request: Request) -> RedirectResponse:
    form = await read_form(request)
    catalog = get_catalog()
    catalog.pop(form.get("category", ""), None)
    save_catalog(catalog)
    return redirect_home()


@app.post("/service/add", dependencies=[Depends(require_admin)])
async def add_service(request: Request) -> RedirectResponse:
    form = await read_form(request)
    category = form.get("category", "")
    name = form.get("name", "")
    description = form.get("description", "")
    if category and name and description:
        photo = await save_uploaded_photo(request)
        catalog = get_catalog()
        catalog.setdefault(category, {})[name] = make_service(description, photo)
        save_catalog(catalog)
    return redirect_home()


@app.post("/service/update", dependencies=[Depends(require_admin)])
async def update_service(request: Request) -> RedirectResponse:
    form = await read_form(request)
    category = form.get("category", "")
    old_name = form.get("old_name", "")
    new_name = form.get("name", "")
    description = form.get("description", "")
    catalog = get_catalog()
    if category in catalog and old_name in catalog[category] and new_name and description:
        current_photo = get_service_photo(catalog[category][old_name])
        photo = await save_uploaded_photo(request, current_photo=current_photo)
        if old_name != new_name:
            catalog[category].pop(old_name, None)
        catalog[category][new_name] = make_service(description, photo)
        save_catalog(catalog)
    return redirect_home()


@app.post("/service/delete", dependencies=[Depends(require_admin)])
async def delete_service(request: Request) -> RedirectResponse:
    form = await read_form(request)
    catalog = get_catalog()
    category = form.get("category", "")
    name = form.get("name", "")
    if category in catalog:
        if name in catalog[category]:
            delete_photo_file(get_service_photo(catalog[category][name]))
        catalog[category].pop(name, None)
        save_catalog(catalog)
    return redirect_home()


@app.post("/service/photo/delete", dependencies=[Depends(require_admin)])
async def delete_service_photo(request: Request) -> RedirectResponse:
    form = await read_form(request)
    catalog = get_catalog()
    category = form.get("category", "")
    name = form.get("name", "")
    if category in catalog and name in catalog[category]:
        description = get_service_description(catalog[category][name])
        photo = get_service_photo(catalog[category][name])
        delete_photo_file(photo)
        catalog[category][name] = make_service(description, "")
        save_catalog(catalog)
    return redirect_home()


@app.post("/action/add", dependencies=[Depends(require_admin)])
async def add_action(request: Request) -> RedirectResponse:
    form = await read_form(request)
    title = form.get("title", "")
    response = form.get("response", "")
    if title and response:
        actions = get_actions()
        actions.append({"title": title, "response": response})
        save_actions(actions)
    return redirect_home()


@app.post("/action/update", dependencies=[Depends(require_admin)])
async def update_action(request: Request) -> RedirectResponse:
    form = await read_form(request)
    actions = get_actions()
    try:
        index = int(form.get("index", "-1"))
    except ValueError:
        return redirect_home()
    if 0 <= index < len(actions) and form.get("title") and form.get("response"):
        actions[index] = {
            "title": form["title"],
            "response": form["response"],
        }
        save_actions(actions)
    return redirect_home()


@app.post("/action/delete", dependencies=[Depends(require_admin)])
async def delete_action(request: Request) -> RedirectResponse:
    form = await read_form(request)
    actions = get_actions()
    try:
        index = int(form.get("index", "-1"))
    except ValueError:
        return redirect_home()
    if 0 <= index < len(actions):
        actions.pop(index)
        save_actions(actions)
    return redirect_home()
