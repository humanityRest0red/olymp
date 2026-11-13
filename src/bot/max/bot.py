"""MAX implementation of the Olymp school exchange bot (long polling)."""
import json
import logging
import time
from datetime import datetime

import requests

from domain import Student
from repository.repo_interface import RepositoryInterface
from .settings import SCHOOLS, SCHOOL_PAGE_SIZE, SHOP_ITEMS, TASKS

LOG = logging.getLogger(__name__)
API = 'https://platform-api2.max.ru'


def button(text, payload):
    return {'type': 'callback', 'text': text, 'payload': payload}


def keyboard(rows):
    return {'type': 'inline_keyboard', 'payload': {'buttons': rows}}


class MaxBotApi:
    def __init__(self, token: str, admin_user_id: int, admin_username: str, repo: RepositoryInterface):
        self.session = requests.Session()
        self.session.headers.update({'Authorization': token})
        self.admin_user_id = admin_user_id
        self.admin_username = admin_username
        self.repo = repo
        self.states = {}  # per-user steps; restarting bot resets unfinished dialogs
        self.pending_purchase = {}
        self.pending_report = {}
        self.marker = None

    def api(self, method, path, *, params=None, data=None, timeout=35):
        response = self.session.request(method, API + path, params=params, json=data, timeout=timeout)
        response.raise_for_status()
        return response.json() if response.content else {}

    def send(self, user_id, text, rows=None, media=None):
        payload = {'text': text[:4000]}
        attachments = []
        if media:
            attachments.append(media)
        if rows:
            attachments.append(keyboard(rows))
        if attachments:
            payload['attachments'] = attachments
        return self.api('POST', '/messages', params={'user_id': int(user_id)}, data=payload)

    def edit(self, message_id, text, rows=None):
        body = {'text': text[:4000], 'attachments': [keyboard(rows)] if rows else []}
        return self.api('PUT', '/messages', params={'message_id': message_id}, data=body)

    def answer(self, callback_id, text=None):
        body = {'notification': text[:200]} if text else {}
        try:
            self.api('POST', '/answers', params={'callback_id': callback_id}, data=body)
        except requests.RequestException:
            LOG.exception('Callback answer failed')

    @staticmethod
    def menu():
        return [[button('👤 Профиль', 'menu:profile'), button('🏆 Топ', 'menu:top')],
                [button('📚 Задания', 'menu:tasks')], [button('🔄 Школьный обменник', 'menu:shop')]]

    @staticmethod
    def top_menu():
        return [[button('💰 Топ баланс', 'menu:top_balance'), button('📝 Топ задания', 'menu:top_tasks')],
                [button('⬅️ Назад', 'menu:home')]]

    def start(self, uid):
        self.states.pop(uid, None)
        user = self.repo.get_student_by_id(uid)
        if user:
            self.send(uid, f'С возвращением, {user.first_name}! 👋', self.menu())
        else:
            self.states[uid] = {'stage': 'first_name'}
            self.send(uid, 'Привет! 👋 Давай зарегистрируемся.\n\nВведи своё имя:')

    def school_page(self, uid, page=0):
        pages = max(1, (len(SCHOOLS) + SCHOOL_PAGE_SIZE - 1) // SCHOOL_PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        rows = [[button(name, f'school_pick:{idx}')]
                for idx, name in enumerate(SCHOOLS[page*SCHOOL_PAGE_SIZE:(page+1)*SCHOOL_PAGE_SIZE],
                                           start=page*SCHOOL_PAGE_SIZE)]
        nav = []
        if page > 0:
            nav.append(button('⬅️ Назад', f'school_page:{page-1}'))
        if page < pages-1:
            nav.append(button('Вперёд ➡️', f'school_page:{page+1}'))
        if nav:
            rows.append(nav)
        self.send(uid, f'🏫 Выбери свою школу (страница {page+1} из {pages}):', rows)

    def registration_input(self, uid, text):
        state = self.states[uid]
        stage = state['stage']
        value = text.strip()
        max_length = 10 if stage == 'class' else 50
        if not 1 <= len(value) <= max_length:
            self.send(uid, f'Введи значение от 1 до {max_length} символов:')
            return
        if stage == 'first_name':
            state.update(first_name=value, stage='last_name')
            self.send(uid, 'Теперь введи фамилию:')
        elif stage == 'last_name':
            state.update(last_name=value, stage='school')
            self.school_page(uid)
        elif stage == 'class':
            user = Student(uid, state['first_name'], state['last_name'], state['school'], value)
            self.repo.save_student(user)
            self.states.pop(uid, None)
            self.send(uid, f'✅ Регистрация завершена!\n\n👤 {user.first_name} {user.last_name}\n🏫 Школа: {user.school}\n🎓 Класс: {value}\n\nДобро пожаловать в Школьный обменник!', self.menu())

    def profile(self, uid):
        user = self.repo.get_student_by_id(uid)
        if not user:
            return self.send(uid, 'Сначала пройди регистрацию: /start')
        self.send(uid, f'👤 Профиль\n\nИмя: {user.first_name}\nФамилия: {user.last_name}\nШкола: {user.school}\nКласс: {user.class_name}\n\n💰 Баланс Школкоинов: {user.balance}\n⭐ Уровень: {user.level} ({user.xp}/{user.xp_next} Опыта)', self.menu())

    def shop(self, uid):
        user = self.repo.get_student_by_id(uid)
        if not user:
            return self.send(uid, 'Сначала пройди регистрацию: /start')
        text = f'🔄 Школьный обменник\n\n💰 Твой баланс: {user.balance} Школкоинов\n\nВыбери товар:\n'
        rows = []
        for idx, (name, item) in enumerate(SHOP_ITEMS.items()):
            text += f'\n• {name} — {item["price"]} 💰\n  {item["desc"]}'
            rows.append([button(f'{name} — {item["price"]} 💰', f'shop_buy:{idx}')])
        self.send(uid, text, rows)

    def tasks(self, uid):
        if not self.repo.get_student_by_id(uid):
            return self.send(uid, 'Сначала пройди регистрацию: /start')
        text = '📚 Задания\n\nВыбери задание и отправь отчёт (фото или текст):\n'
        rows = []
        for tid, task in TASKS.items():
            text += f'\n#{tid} {task["name"]}\n   💰 {task["reward_coins"]} Школкоинов | ⭐ {task["reward_xp"]} Опыта\n'
            rows.append([button(f'#{tid} {task["name"]} (+{task["reward_coins"]}💰 +{task["reward_xp"]}⭐)', f'task_pick:{tid}')])
        self.send(uid, text, rows)

    @staticmethod
    def get_media(message):
        body = message.get('body') or {}
        for attachment in body.get('attachments') or []:
            kind = attachment.get('type')
            if kind not in ('image', 'file'):
                continue
            payload = attachment.get('payload') or {}
            token = payload.get('token')
            if kind == 'image' and not token:
                photos = payload.get('photos') or {}
                if isinstance(photos, dict):
                    token = next((p.get('token') for p in photos.values() if isinstance(p, dict) and p.get('token')), None)
            if token:
                return kind, json.dumps({'type': kind, 'token': token})
            # URL is a fallback for pictures when MAX does not include reusable token.
            if kind == 'image' and payload.get('url'):
                return kind, json.dumps({'type': kind, 'url': payload['url']})
        return None, None

    def report_input(self, uid, message):
        task_id = self.pending_report.get(uid)
        task = TASKS.get(task_id)
        if not task:
            self.pending_report.pop(uid, None)
            return
        kind, media_ref = self.get_media(message)
        text = ((message.get('body') or {}).get('text') or '').strip()
        if not kind and not text:
            return self.send(uid, '❌ Отправь фото, документ или текст.')
        rid = self.repo.create_report(uid, task_id, task['name'], kind or 'text', text, media_ref)
        self.pending_report.pop(uid, None)
        user = self.repo.get_student_by_id(uid)
        self.send(uid, '✅ Отчёт отправлен на проверку! Ожидай решения администратора.', self.menu())
        header = (f'📥 Новая заявка №{rid}\n\n👤 {user.first_name} {user.last_name} ({uid})\n'
                  f'🏫 {user.school}, {user.class_name}\n📝 Задание: {task["name"]}\n'
                  f'💰 {task["reward_coins"]} Школкоинов | ⭐ {task["reward_xp"]} XP\n\n')
        self.send_report_to_admin(self.admin_user_id, rid, header, text, media_ref)

    def send_report_to_admin(self, uid, rid, header, text, media_ref):
        rows = [[button('✅ Одобрить', f'adm_approve:{rid}'), button('❌ Отклонить', f'adm_reject:{rid}')]]
        media = json.loads(media_ref) if media_ref else None
        attachment = None
        if media:
            if media.get('token'):
                attachment = {'type': media['type'], 'payload': {'token': media['token']}}
            elif media.get('url') and media['type'] == 'image':
                attachment = {'type': 'image', 'payload': {'url': media['url']}}
        try:
            self.send(uid, header + (f'Текст отчёта:\n{text}' if text else ''), rows, attachment)
        except requests.RequestException:
            LOG.exception('Unable to send media report; retrying as text')
            self.send(uid, header + f'Текст отчёта:\n{text}\nВложение не удалось переслать.', rows)

    def admin_panel(self, uid):
        if uid != self.admin_user_id:
            return self.send(uid, '⛔ Нет доступа.')
        pending = self.repo.get_pending_reports()
        history = self.repo.get_report_history(limit=10)
        lines = [f'🛡 АДМИН-ПАНЕЛЬ\n\n📥 Активных заявок: {len(pending)}', 'Для выхода: /exitadminpanel', '\n— Ожидают проверки:']
        lines += [f'№{r["id"]} → user {r["user_id"]} | {r["task_name"]}' for r in pending[:20]] or ['✅ Нет активных заявок.']
        lines += ['\n— История (последние 10):']
        lines += [f'{"✅" if r["status"] == "approved" else "❌"} №{r["id"]} user {r["user_id"]} → {r["task_name"]}' for r in history] or ['Пусто.']
        self.send(uid, '\n'.join(lines))
        for r in pending[:10]:
            header = f'📥 Заявка №{r["id"]}\n👤 user {r["user_id"]} | {r["task_name"]}\n🕒 {r["created_at"]}\n'
            self.send_report_to_admin(uid, r['id'], header, r.get('report_text') or '', r.get('report_file'))

    def text_update(self, msg):
        uid = int(msg['sender']['user_id'])
        if msg['sender'].get('is_bot'):
            return
        text = ((msg.get('body') or {}).get('text') or '').strip()
        if text in ('/start', '/start@bot'):
            return self.start(uid)
        if text == '/admpanel':
            return self.admin_panel(uid)
        if text == '/exitadminpanel':
            return self.send(uid, 'Вы вышли из админ-панели.', self.menu()) if uid == self.admin_user_id else None
        if uid in self.pending_report:
            if text == '/cancel':
                self.pending_report.pop(uid, None)
                return self.send(uid, 'Отправка отчёта отменена.', self.menu())
            return self.report_input(uid, msg)
        if uid in self.states:
            if text == '/cancel':
                self.states.pop(uid, None)
                return self.send(uid, 'Регистрация отменена.')
            if self.states[uid]['stage'] in ('first_name', 'last_name', 'class'):
                return self.registration_input(uid, text)
            return self.send(uid, 'Выбери школу кнопкой выше. Или /cancel для отмены.')
        commands = {'👤 Профиль': self.profile, '🏆 Топ': lambda u: self.send(u, 'Выбери категорию топа:', self.top_menu()),
                    '📚 Задания': self.tasks, '🔄 Школьный обменник': self.shop,
                    '⬅️ Назад': lambda u: self.send(u, 'Главное меню:', self.menu())}
        if text in commands:
            return commands[text](uid)
        if text in ('💰 Топ баланс', '📝 Топ задания'):
            return self.send(uid, f'{text} — 🚧 в разработке', self.top_menu())
        self.send(uid, 'Выбери действие:', self.menu())

    def callback_update(self, update):
        callback = update['callback']
        uid = int(callback['user']['user_id'])
        cid = callback['callback_id']
        payload = callback.get('payload') or ''
        if payload.startswith('menu:'):
            action = payload[5:]
            mapping = {'profile': self.profile, 'tasks': self.tasks, 'shop': self.shop,
                       'top': lambda u: self.send(u, 'Выбери категорию топа:', self.top_menu()),
                       'home': lambda u: self.send(u, 'Главное меню:', self.menu()),
                       'top_balance': lambda u: self.send(u, '💰 Топ баланс — 🚧 в разработке', self.top_menu()),
                       'top_tasks': lambda u: self.send(u, '📝 Топ задания — 🚧 в разработке', self.top_menu())}
            if action in mapping:
                mapping[action](uid)
        elif payload.startswith('school_page:'):
            if uid in self.states and self.states[uid]['stage'] == 'school':
                self.school_page(uid, int(payload.split(':')[1]))
        elif payload.startswith('school_pick:'):
            state = self.states.get(uid)
            idx = int(payload.split(':')[1])
            if state and state['stage'] == 'school' and 0 <= idx < len(SCHOOLS):
                state.update(stage='class', school=SCHOOLS[idx])
                self.send(uid, f'🏫 {SCHOOLS[idx]}\nИ последнее — класс (например: 9А):')
            else:
                self.send(uid, 'Начни регистрацию: /start')
        elif payload.startswith('shop_buy:'):
            idx = int(payload.split(':')[1])
            if 0 <= idx < len(SHOP_ITEMS):
                name = list(SHOP_ITEMS)[idx]
                user = self.repo.get_student_by_id(uid)
                item = SHOP_ITEMS[name]
                if not user:
                    self.send(uid, 'Сначала /start')
                elif user.balance < item['price']:
                    self.send(uid, '❌ Недостаточно Школкоинов!')
                else:
                    self.pending_purchase[uid] = name
                    self.send(uid, f'🛒 Подтверждение покупки\n\nТовар: {name}\nЦена: {item["price"]} Школкоинов\nТвой баланс: {user.balance} 💰\nПосле покупки: {user.balance-item["price"]} 💰\n\nПодтверждаешь?',
                              [[button('✅ Подтвердить', f'shop_confirm:{idx}'), button('❌ Отмена', 'shop_cancel')]])
        elif payload == 'shop_cancel':
            self.pending_purchase.pop(uid, None)
            self.send(uid, '❌ Покупка отменена.', self.menu())
        elif payload.startswith('shop_confirm:'):
            idx = int(payload.split(':')[1])
            if 0 <= idx < len(SHOP_ITEMS):
                name = list(SHOP_ITEMS)[idx]
                user = self.repo.get_student_by_id(uid)
                item = SHOP_ITEMS[name]
                if self.pending_purchase.get(uid) != name:
                    self.send(uid, 'Подтверждение устарело. Выбери товар заново.')
                elif user is None or user.balance < item['price']:
                    self.send(uid, '❌ Недостаточно Школкоинов или не пройдена регистрация.')
                else:
                    self.repo.update_balance(uid, -item['price'])
                    self.repo.add_purchase(uid, name, item['price'])
                    self.pending_purchase.pop(uid, None)
                    self.send(uid, f'✅ Покупка оформлена!\n\nТовар: {name}\nСписано: {item["price"]} 💰\nОстаток: {user.balance-item["price"]} 💰\nАдминистратор {self.admin_username} уведомлён и свяжется с тобой.', self.menu())
                    try:
                        self.send(self.admin_user_id, f'🛒 Новая покупка\n\n👤 {user.first_name} {user.last_name}\n🆔 ID: {uid}\n🏫 {user.school}, {user.class_name}\n📦 {name} ({item["price"]} 💰)\n📅 {datetime.now():%d.%m.%Y %H:%M}')
                    except requests.RequestException:
                        LOG.exception('Admin purchase notification failed')
        elif payload.startswith('task_pick:'):
            tid = int(payload.split(':')[1]); task = TASKS.get(tid)
            user = self.repo.get_student_by_id(uid)
            if not task or not user:
                self.send(uid, 'Сначала зарегистрируйся или выбери другое задание.')
            elif self.repo.has_pending_for(uid, tid):
                self.send(uid, '⏳ Заявка уже на проверке!')
            else:
                blocked, seconds = self.repo.has_recent_rejected(uid, tid, cooldown=300)
                if blocked:
                    self.send(uid, f'⛔ Повторить можно через {seconds//60}м {seconds%60}с.')
                else:
                    self.pending_report[uid] = tid
                    self.send(uid, f'📤 Отправка отчёта\n\nЗадание: {task["name"]}\nНаграда: {task["reward_coins"]} 💰 + {task["reward_xp"]} ⭐\n\nОтправь фото, документ или текст. /cancel — отмена.')
        elif payload.startswith(('adm_approve:', 'adm_reject:')):
            if uid != self.admin_user_id:
                self.send(uid, '⛔ Нет доступа.')
            else:
                approve = payload.startswith('adm_approve:')
                rid = int(payload.split(':')[1]); report = self.repo.get_report(rid)
                if not report or report['status'] != 'pending':
                    self.send(uid, 'Заявка уже обработана.')
                else:
                    task = TASKS.get(report['task_id'])
                    if approve and not task:
                        self.send(uid, 'Задание не найдено.')
                    else:
                        self.repo.set_report_status(rid, 'approved' if approve else 'rejected')
                        if approve:
                            self.repo.update_progress(report['user_id'], task['reward_xp'], task['reward_coins'])
                        self.send(uid, f'{"✅" if approve else "❌"} Заявка №{rid} {"одобрена" if approve else "отклонена"}.')
                        try:
                            if approve:
                                self.send(report['user_id'], f'🎉 Задание одобрено!\n\n📝 {task["name"]}\n💰 +{task["reward_coins"]} Школкоинов\n⭐ +{task["reward_xp"]} Опыта')
                            else:
                                self.send(report['user_id'], f'❌ Задание отклонено\n\n📝 {report["task_name"]}\nПовторная попытка доступна через 5 минут.')
                        except requests.RequestException:
                            LOG.exception('User notification failed')
        self.answer(cid)

    def handle_update(self, update):
        kind = update.get('update_type')
        if kind == 'message_created' and update.get('message'):
            self.text_update(update['message'])
        elif kind == 'message_callback' and update.get('callback'):
            self.callback_update(update)
        elif kind == 'bot_started':
            user = update.get('user') or {}
            if user.get('user_id'):
                self.start(int(user['user_id']))

    def run(self):
        LOG.info('MAX bot started')
        while True:
            try:
                params = {'timeout': 30, 'limit': 100}
                if self.marker is not None:
                    params['marker'] = self.marker
                result = self.api('GET', '/updates', params=params, timeout=40)
                for update in result.get('updates') or []:
                    try:
                        self.handle_update(update)
                    except Exception:
                        LOG.exception('Update handler failed: %s', update.get('update_type'))
                self.marker = result.get('marker', self.marker)
            except requests.RequestException:
                LOG.exception('MAX polling failed, retrying')
                time.sleep(5)
