from datetime import datetime
import telebot
from telebot import types

from repository.repo_interface import RepositoryInterface
from .settings import SCHOOLS, SCHOOL_PAGE_SIZE, TASKS, SHOP_ITEMS 


class TelebotApi:
    def __init__(self, token: str, admin_chat_id: int, admin_username: str, repo: RepositoryInterface):
        self.bot = telebot.TeleBot(token)
        self.admin_chat_id = admin_chat_id
        self.admin_username = admin_username
        self.repo = repo
        self.admin_panel_active = set()
        self.pending_purchase = {}
        self.pending_report = {}
        self.pending_registration = {}
        self._register_handlers()

    def _register_handlers(self):
        b = self.bot
        b.message_handler(commands=["start"])(self.cmd_start)
        b.message_handler(commands=["admpanel"])(self.cmd_admpanel)
        b.message_handler(commands=["exitadminpanel"])(self.cmd_exit_admin)

        b.message_handler(func=lambda m: m.text == "👤 Профиль")(self.show_profile)
        b.message_handler(func=lambda m: m.text == "🏆 Топ")(self.show_top)
        b.message_handler(func=lambda m: m.text == "📚 Задания")(self.show_tasks)
        b.message_handler(func=lambda m: m.text == "🔄 Школьный обменник")(self.show_shop)

        b.message_handler(func=lambda m: m.text == "⬅️ Назад")(self.back_to_main)
        b.message_handler(func=lambda m: m.text in ("💰 Топ баланс", "📝 Топ задания"))(self.top_in_dev)

        b.callback_query_handler(func=lambda c: c.data.startswith("school_page:"))(self.cb_school_page)
        b.callback_query_handler(func=lambda c: c.data.startswith("school_pick:"))(self.cb_school_pick)
        b.callback_query_handler(func=lambda c: c.data.startswith("shop_buy:"))(self.cb_shop_buy)
        b.callback_query_handler(func=lambda c: c.data.startswith("shop_confirm:"))(self.cb_shop_confirm)
        b.callback_query_handler(func=lambda c: c.data == "shop_cancel")(self.cb_shop_cancel)
        b.callback_query_handler(func=lambda c: c.data.startswith("task_pick:"))(self.cb_task_pick)
        b.callback_query_handler(func=lambda c: c.data.startswith("adm_approve:"))(self.cb_adm_approve)
        b.callback_query_handler(func=lambda c: c.data.startswith("adm_reject:"))(self.cb_adm_reject)

    # ---------- клавиатуры ----------
    @staticmethod
    def main_menu():
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("👤 Профиль")
        kb.row("🏆 Топ")
        kb.row("📚 Задания", "🔄 Школьный обменник")
        return kb

    @staticmethod
    def top_menu():
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("💰 Топ баланс", "📝 Топ задания")
        kb.row("⬅️ Назад")
        return kb

    @staticmethod
    def shop_menu():
        kb = types.InlineKeyboardMarkup(row_width=1)
        for name, info in SHOP_ITEMS.items():
            kb.add(types.InlineKeyboardButton(
                f"{name} — {info['price']} Школкоинов",
                callback_data=f"shop_buy:{name}"
            ))
        return kb

    @staticmethod
    def tasks_menu():
        kb = types.InlineKeyboardMarkup(row_width=1)
        for tid, t in TASKS.items():
            kb.add(types.InlineKeyboardButton(
                f"#{tid} {t['name']}  (+{t['reward_coins']}💰 +{t['reward_xp']}⭐)",
                callback_data=f"task_pick:{tid}"
            ))
        return kb

    # ---------- /start ----------
    def cmd_start(self, message):
        user = self.repo.get_student_by_id(message.from_user.id)
        if user:
            self.bot.send_message(message.chat.id,
                f"С возвращением, {user.first_name}! 👋",
                reply_markup=self.main_menu())
            return
        self.bot.send_message(message.chat.id,
            "Привет! 👋 Давай зарегистрируемся.\n\nВведи своё **имя**:",
            parse_mode="Markdown")
        self.bot.register_next_step_handler(message, self.reg_first_name)

    def reg_first_name(self, message):
        first_name = (message.text or "").strip()
        if not 1 <= len(first_name) <= 50:
            self.bot.send_message(message.chat.id, "Имя должно быть от 1 до 50 символов. Попробуй ещё раз:")
            self.bot.register_next_step_handler(message, self.reg_first_name)
            return
        self.bot.send_message(message.chat.id, "Теперь введи **фамилию**:", parse_mode="Markdown")
        self.bot.register_next_step_handler(message, self.reg_last_name, first_name)

    def reg_last_name(self, message, first_name):
        last_name = (message.text or "").strip()
        if not 1 <= len(last_name) <= 50:
            self.bot.send_message(message.chat.id, "Фамилия от 1 до 50 символов. Попробуй ещё раз:")
            self.bot.register_next_step_handler(message, self.reg_last_name, first_name)
            return
        self.pending_registration[message.from_user.id] = {
            "first_name": first_name,
            "last_name": last_name,
        }
        self.send_school_page(message.chat.id, page=0)

    def send_school_page(self, chat_id, page=0):
        """Показывает список заранее заданных школ с постраничной навигацией."""
        total_pages = (len(SCHOOLS) + SCHOOL_PAGE_SIZE - 1) // SCHOOL_PAGE_SIZE
        page = max(0, min(page, total_pages - 1))
        start = page * SCHOOL_PAGE_SIZE
        page_schools = SCHOOLS[start:start + SCHOOL_PAGE_SIZE]

        kb = types.InlineKeyboardMarkup(row_width=1)
        for index, school in enumerate(page_schools, start=start):
            kb.add(types.InlineKeyboardButton(
                school,
                callback_data=f"school_pick:{index}"
            ))

        nav = []
        if page > 0:
            nav.append(types.InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"school_page:{page - 1}"
            ))
        if page < total_pages - 1:
            nav.append(types.InlineKeyboardButton(
                "Вперёд ➡️",
                callback_data=f"school_page:{page + 1}"
            ))
        if nav:
            kb.row(*nav)

        self.bot.send_message(
            chat_id,
            f"🏫 Выбери свою школу (страница {page + 1} из {total_pages}):",
            reply_markup=kb
        )

    def cb_school_page(self, call):
        page = int(call.data.split(":")[1])
        if call.from_user.id not in self.pending_registration:
            self.bot.answer_callback_query(call.id, "Начни регистрацию командой /start", show_alert=True)
            return
        self.send_school_page(call.message.chat.id, page=page)
        self.bot.answer_callback_query(call.id)

    def cb_school_pick(self, call):
        school_index = int(call.data.split(":")[1])
        registration = self.pending_registration.get(call.from_user.id)
        if registration is None:
            self.bot.answer_callback_query(call.id, "Начни регистрацию командой /start", show_alert=True)
            return

        if not 0 <= school_index < len(SCHOOLS):
            self.bot.answer_callback_query(call.id, "Школа не найдена", show_alert=True)
            return

        school = SCHOOLS[school_index]
        self.bot.answer_callback_query(call.id, f"Выбрана: {school}")
        self.bot.send_message(
            call.message.chat.id,
            "И последнее — **класс** (например: 9А):",
            parse_mode="Markdown"
        )
        self.bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            self.reg_class,
            registration["first_name"],
            registration["last_name"],
            school
        )
        self.pending_registration.pop(call.from_user.id, None)

    def reg_class(self, message, first_name, last_name, school):
        user_class = (message.text or "").strip()
        if not 1 <= len(user_class) <= 10:
            self.bot.send_message(message.chat.id, "Класс указан некорректно. Попробуй ещё раз:")
            self.bot.register_next_step_handler(message, self.reg_class, first_name, last_name, school)
            return

        self.repo.save_student(Student(
            user_id=message.from_user.id,
            first_name=first_name,
            last_name=last_name,
            school=school,
            class_name=user_class,
        ))

        self.bot.send_message(message.chat.id,
            f"✅ Регистрация завершена!\n\n"
            f"👤 {first_name} {last_name}\n"
            f"🏫 Школа: {school}\n"
            f"🎓 Класс: {user_class}\n\n"
            f"Добро пожаловать в Школьный обменник!",
            reply_markup=self.main_menu())

    # ---------- профиль ----------
    def show_profile(self, message) -> None:
        user = self.repo.get_student_by_id(message.from_user.id)
        if not user:
            self.bot.send_message(message.chat.id, "Сначала пройди регистрацию: /start")
            return
        self.bot.send_message(message.chat.id,
            f"👤 *Профиль*\n\n"
            f"Имя: {user.first_name}\n"
            f"Фамилия: {user.last_name}\n"
            f"Школа: {user.school}\n"
            f"Класс: {user.class_name}\n\n"
            f"💰 Баланс Школкоинов: {user.balance}\n"
            f"⭐ Уровень: {user.level} ({user.xp}/{user.xp_next} Опыта)",
            parse_mode="Markdown")

    # ---------- топ ----------
    def show_top(self, message):
        self.bot.send_message(message.chat.id, "Выбери категорию топа:", reply_markup=self.top_menu())

    def back_to_main(self, message):
        self.bot.send_message(message.chat.id, "Главное меню:", reply_markup=self.main_menu())

    def top_in_dev(self, message):
        self.bot.send_message(message.chat.id, f"{message.text} — 🚧 в разработке",
                              reply_markup=self.top_menu())

    # ==================== ОБМЕННИК ====================
    def show_shop(self, message):
        user = self.repo.get_student_by_id(message.from_user.id)
        if not user:
            self.bot.send_message(message.chat.id, "Сначала пройди регистрацию: /start")
            return
        text = (
            f"🔄 *Школьный обменник*\n\n"
            f"💰 Твой баланс: *{user.balance}* Школкоинов\n\n"
            f"Выбери товар:\n"
        )
        for name, info in SHOP_ITEMS.items():
            text += f"\n• *{name}* — {info['price']} 💰\n  _{info['desc']}_"
        self.bot.send_message(message.chat.id, text, parse_mode="Markdown",
                              reply_markup=self.shop_menu())

    def cb_shop_buy(self, call):
        item_name = call.data.split(":", 1)[1]
        user_id = call.from_user.id
        user = self.repo.get_student_by_id(user_id)
        if not user:
            self.bot.answer_callback_query(call.id, "Сначала /start")
            return
        if item_name not in SHOP_ITEMS:
            self.bot.answer_callback_query(call.id, "Товар не найден")
            return

        item = SHOP_ITEMS[item_name]
        if user.balance < item["price"]:
            self.bot.answer_callback_query(call.id, "❌ Недостаточно Школкоинов!", show_alert=True)
            return

        self.pending_purchase[user_id] = item_name
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"shop_confirm:{item_name}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="shop_cancel"),
        )
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(f"🛒 *Подтверждение покупки*\n\n"
                  f"Товар: *{item_name}*\n"
                  f"Цена: *{item['price']}* Школкоинов\n"
                  f"Твой баланс: *{user.balance}* 💰\n"
                  f"После покупки: *{user.balance - item['price']}* 💰\n\n"
                  f"Подтверждаешь?"),
            parse_mode="Markdown",
            reply_markup=kb,
        )

    def cb_shop_cancel(self, call):
        self.pending_purchase.pop(call.from_user.id, None)
        self.bot.answer_callback_query(call.id, "Отменено")
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Покупка отменена.",
        )

    def cb_shop_confirm(self, call):
        user_id = call.from_user.id
        item_name = call.data.split(":", 1)[1]
        user = self.repo.get_student_by_id(user_id)
        if not user:
            self.bot.answer_callback_query(call.id, "Сначала /start")
            return
        item = SHOP_ITEMS.get(item_name)
        if not item:
            self.bot.answer_callback_query(call.id, "Товар не найден")
            return
        if user.balance < item["price"]:
            self.bot.answer_callback_query(call.id, "❌ Недостаточно Школкоинов!", show_alert=True)
            return

        self.repo.update_balance(user_id, -item["price"])
        self.repo.add_purchase(user_id, item_name, item["price"])
        self.pending_purchase.pop(user_id, None)

        new_balance = user.balance - item["price"]

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(f"✅ *Покупка оформлена!*\n\n"
                  f"Товар: *{item_name}*\n"
                  f"Списано: *{item['price']}* 💰\n"
                  f"Остаток: *{new_balance}* 💰\n\n"
                  f"Администратор {self.admin_username} уже уведомлён и свяжется с тобой."),
            parse_mode="Markdown",
        )
        self.bot.answer_callback_query(call.id, "Покупка оформлена!")

        try:
            self.bot.send_message(
                self.admin_chat_id,
                f"🛒 *Новая покупка*\n\n"
                f"👤 Пользователь: {user.first_name} {user.last_name}\n"
                f"🆔 ID: `{user_id}`\n"
                f"🏫 Школа: {user.school}, класс: {user.class_name}\n"
                f"📦 Товар: *{item_name}* ({item['price']} 💰)\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="Markdown",
            )
        except Exception as e:
            print("Не удалось уведомить админа:", e)

    # ==================== ЗАДАНИЯ ====================
    def show_tasks(self, message):
        user = self.repo.get_student_by_id(message.from_user.id)
        if not user:
            self.bot.send_message(message.chat.id, "Сначала пройди регистрацию: /start")
            return
        text = "📚 *Задания*\n\nВыбери задание и отправь отчёт (фото или текст):\n"
        for tid, t in TASKS.items():
            text += (f"\n*#{tid}* {t['name']}\n"
                     f"   💰 {t['reward_coins']} Школкоинов  |  ⭐ {t['reward_xp']} Опыта")
        self.bot.send_message(message.chat.id, text, parse_mode="Markdown",
                              reply_markup=self.tasks_menu())

    def cb_task_pick(self, call):
        user_id = call.from_user.id
        task_id = int(call.data.split(":", 1)[1])
        task = TASKS.get(task_id)
        if not task:
            self.bot.answer_callback_query(call.id, "Задание не найдено")
            return
        user = self.repo.get_student_by_id(user_id)
        if not user:
            self.bot.answer_callback_query(call.id, "Сначала /start")
            return

        if self.repo.has_pending_for(user_id, task_id):
            self.bot.answer_callback_query(call.id, "⏳ Заявка уже на проверке!", show_alert=True)
            return

        blocked, remain = self.repo.has_recent_rejected(user_id, task_id, cooldown=300)
        if blocked:
            m, s = divmod(remain, 60)
            self.bot.answer_callback_query(call.id, f"⛔ Отказ. Повтори через {m}м {s}с.", show_alert=True)
            return

        self.pending_report[user_id] = task_id
        self.bot.send_message(
            chat_id=call.message.chat.id,
            text=(f"📤 *Отправка отчёта*\n\n"
                  f"Задание: *{task['name']}*\n"
                  f"Награда: *{task['reward_coins']}* 💰 + *{task['reward_xp']}* ⭐\n\n"
                  f"Отправь фото или текст с подтверждением."),
            parse_mode="Markdown",
        )
        self.bot.register_next_step_handler_by_chat_id(call.message.chat.id, self.receive_report, task_id)
        self.bot.answer_callback_query(call.id)

    def receive_report(self, message, task_id):
        user_id = message.from_user.id
        if self.pending_report.get(user_id) != task_id:
            return

        task = TASKS.get(task_id)
        if not task:
            return

        report_type, report_text, report_file = None, None, None
        if message.photo:
            report_type = "photo"
            report_file = message.photo[-1].file_id
            report_text = message.caption or ""
        elif message.document:
            report_type = "document"
            report_file = message.document.file_id
            report_text = message.caption or ""
        elif message.text:
            report_type = "text"
            report_text = message.text
        else:
            self.bot.send_message(message.chat.id, "❌ Отправь фото или текст.")
            self.bot.register_next_step_handler_by_chat_id(message.chat.id, self.receive_report, task_id)
            return

        rid = self.repo.create_report(user_id, task_id, task["name"],
                                      report_type, report_text, report_file)
        self.pending_report.pop(user_id, None)
        user = self.repo.get_student_by_id(user_id)

        self.bot.send_message(message.chat.id,
            "✅ Отчёт отправлен на проверку! Ожидай решения администратора.")

        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_approve:{rid}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_reject:{rid}"),
        )
        header = (f"📥 *Новая заявка №{rid}*\n\n"
                  f"👤 {user.first_name} {user.last_name} (`{user_id}`)\n"
                  f"🏫 {user.school}, {user.class_name}\n"
                  f"📝 Задание: *{task['name']}*\n"
                  f"💰 {task['reward_coins']} Школкоинов | ⭐ {task['reward_xp']} XP\n\n")
        try:
            if report_type == "photo":
                self.bot.send_photo(self.admin_chat_id, report_file,
                                    caption=header + f"_{report_text}_",
                                    parse_mode="Markdown", reply_markup=kb)
            elif report_type == "document":
                self.bot.send_document(self.admin_chat_id, report_file,
                                       caption=header + f"_{report_text}_",
                                       parse_mode="Markdown", reply_markup=kb)
            else:
                self.bot.send_message(self.admin_chat_id, header + f"Текст отчёта:\n{report_text}",
                                      parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            print("Не удалось уведомить админа о заявке:", e)

    # ==================== АДМИН-ПАНЕЛЬ ====================
    def cmd_admpanel(self, message):
        if message.from_user.id != self.admin_chat_id:
            self.bot.send_message(message.chat.id, "⛔ Нет доступа.")
            return
        self.admin_panel_active.add(message.from_user.id)
        self._send_admin_panel(message.chat.id)

    def cmd_exit_admin(self, message):
        if message.from_user.id != self.admin_chat_id:
            return
        self.admin_panel_active.discard(message.from_user.id)
        self.bot.send_message(message.chat.id, "Вы вышли из админ-панели.",
                              reply_markup=self.main_menu())

    def _send_admin_panel(self, chat_id):
        pending = self.repo.get_pending_reports()
        history = self.repo.get_report_history(limit=10)

        text = f"🛡 *АДМИН-ПАНЕЛЬ*\n\n"
        text += f"📥 Активных заявок: *{len(pending)}*\n"
        text += "Для выхода: /exitadminpanel\n\n"

        if pending:
            text += "— *Ожидают проверки:*\n"
            for r in pending[:20]:
                text += f" №{r['id']} → user `{r['user_id']}` | {r['task_name']}\n"
        else:
            text += "✅ Нет активных заявок.\n"

        text += "\n— *История (последние 10):*\n"
        if history:
            for r in history[:10]:
                mark = "✅" if r["status"] == "approved" else "❌"
                text += f" {mark} №{r['id']} user `{r['user_id']}` → {r['task_name']}\n"
        else:
            text += " Пусто.\n"

        self.bot.send_message(chat_id, text, parse_mode="Markdown")

        for r in pending[:10]:
            self._send_pending_to_admin(chat_id, r)

    def _send_pending_to_admin(self, chat_id, r):
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_approve:{r['id']}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_reject:{r['id']}"),
        )
        header = (f"📥 *Заявка №{r['id']}*\n"
                  f"👤 user `{r['user_id']}` | {r['task_name']}\n"
                  f"🕒 {r['created_at']}\n")
        try:
            if r["report_type"] == "photo":
                self.bot.send_photo(chat_id, r["report_file"],
                                    caption=header + f"\n_{r['report_text'] or ''}_",
                                    parse_mode="Markdown", reply_markup=kb)
            elif r["report_type"] == "document":
                self.bot.send_document(chat_id, r["report_file"],
                                       caption=header + f"\n_{r['report_text'] or ''}_",
                                       parse_mode="Markdown", reply_markup=kb)
            else:
                self.bot.send_message(chat_id, header + f"\nТекст: {r['report_text'] or '—'}",
                                      parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            print("Ошибка отправки заявки:", e)

    def cb_adm_approve(self, call):
        if call.from_user.id != self.admin_chat_id:
            self.bot.answer_callback_query(call.id, "⛔ Нет доступа")
            return
        rid = int(call.data.split(":", 1)[1])
        r = self.repo.get_report(rid)
        if not r or r["status"] != "pending":
            self.bot.answer_callback_query(call.id, "Уже обработана")
            return
        task = TASKS.get(r["task_id"])
        if not task:
            self.bot.answer_callback_query(call.id, "Задание не найдено")
            return

        self.repo.set_report_status(rid, "approved")
        self.repo.update_progress(r["user_id"], task["reward_xp"], task["reward_coins"])

        try:
            self.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                               reply_markup=None)
        except Exception:
            pass

        self.bot.send_message(call.message.chat.id, f"✅ Заявка №{rid} одобрена.")
        self.bot.answer_callback_query(call.id, "Одобрено!")

        try:
            self.bot.send_message(
                r["user_id"],
                f"🎉 *Задание одобрено!*\n\n"
                f"📝 {task['name']}\n"
                f"💰 +{task['reward_coins']} Школкоинов\n"
                f"⭐ +{task['reward_xp']} Опыта",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    def cb_adm_reject(self, call):
        if call.from_user.id != self.admin_chat_id:
            self.bot.answer_callback_query(call.id, "⛔ Нет доступа")
            return
        rid = int(call.data.split(":", 1)[1])
        r = self.repo.get_report(rid)
        if not r or r["status"] != "pending":
            self.bot.answer_callback_query(call.id, "Уже обработана")
            return

        self.repo.set_report_status(rid, "rejected")
        try:
            self.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                               reply_markup=None)
        except Exception:
            pass
        self.bot.send_message(call.message.chat.id, f"❌ Заявка №{rid} отклонена.")
        self.bot.answer_callback_query(call.id, "Отклонено")

        try:
            self.bot.send_message(
                r["user_id"],
                f"❌ *Задание отклонено*\n\n"
                f"📝 {r['task_name']}\n"
                f"Повторная попытка доступна через 5 минут.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    def run(self):
        print("Бот запущен...")
        self.bot.infinity_polling()
