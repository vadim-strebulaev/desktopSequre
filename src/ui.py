from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .db import Capacities, Database
from .validation import (
    validate_card_number,
    validate_name,
    validate_plate,
    validate_positive_int,
)


class MainWindow(QMainWindow):
    def __init__(self, db: Database, base_dir: Path):
        super().__init__()
        self.db = db
        self.base_dir = base_dir

        self.setWindowTitle("Терминал охранника")
        self.resize(860, 560)

        tabs = QTabWidget()
        tabs.addTab(self._build_employee_tab(), "Сотрудники")
        tabs.addTab(self._build_guest_tab(), "Гости")
        tabs.addTab(self._build_parking_tab(), "Парковка")
        tabs.addTab(self._build_settings_tab(), "Настройки")
        self.setCentralWidget(tabs)

        self.overstay_timer = QTimer(self)
        self.overstay_timer.setInterval(30_000)
        self.overstay_timer.timeout.connect(self._check_guest_overstays)
        self.overstay_timer.start()

        self._refresh_parking_list()

    def _error(self, text: str) -> None:
        QMessageBox.critical(self, "Ошибка", text)

    def _info(self, text: str) -> None:
        QMessageBox.information(self, "Информация", text)

    def _build_employee_tab(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)

        form_box = QGroupBox("Регистрация прохода сотрудника")
        form = QFormLayout(form_box)
        self.emp_card = QLineEdit()
        self.emp_first = QLineEdit()
        self.emp_last = QLineEdit()
        form.addRow("Номер пропуска", self.emp_card)
        form.addRow("Имя", self.emp_first)
        form.addRow("Фамилия", self.emp_last)

        btn_row = QHBoxLayout()
        btn_in = QPushButton("Вход")
        btn_out = QPushButton("Выход")
        btn_in.clicked.connect(self._employee_in)
        btn_out.clicked.connect(self._employee_out)
        btn_row.addWidget(btn_in)
        btn_row.addWidget(btn_out)

        layout.addWidget(form_box)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return root

    def _build_guest_tab(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)

        form_box = QGroupBox("Временный пропуск гостя")
        form = QFormLayout(form_box)
        self.guest_pass = QLineEdit()
        self.guest_first = QLineEdit()
        self.guest_last = QLineEdit()
        self.guest_hours = QLineEdit()
        self.guest_hours.setPlaceholderText("Например: 2")
        form.addRow("ID временного пропуска", self.guest_pass)
        form.addRow("Имя", self.guest_first)
        form.addRow("Фамилия", self.guest_last)
        form.addRow("Действует (часы)", self.guest_hours)

        btn_row = QHBoxLayout()
        btn_in = QPushButton("Вход")
        btn_out = QPushButton("Выход")
        btn_check = QPushButton("Проверить просрочки")
        btn_in.clicked.connect(self._guest_in)
        btn_out.clicked.connect(self._guest_out)
        btn_check.clicked.connect(self._check_guest_overstays)
        btn_row.addWidget(btn_in)
        btn_row.addWidget(btn_out)
        btn_row.addWidget(btn_check)

        layout.addWidget(form_box)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return root

    def _build_parking_tab(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)

        form_box = QGroupBox("Парковочные талоны")
        form = QFormLayout(form_box)
        self.park_type = QLineEdit()
        self.park_type.setPlaceholderText("employee или guest")
        self.park_card = QLineEdit()
        self.park_card.setPlaceholderText("для employee: номер пропуска; для guest: можно пусто")
        self.park_plate = QLineEdit()
        form.addRow("Тип (employee/guest)", self.park_type)
        form.addRow("Пропуск/ID", self.park_card)
        form.addRow("Номер авто", self.park_plate)

        btn_row = QHBoxLayout()
        btn_issue = QPushButton("Выдать талон")
        btn_close = QPushButton("Закрыть выбранный")
        btn_refresh = QPushButton("Обновить")
        btn_issue.clicked.connect(self._issue_ticket)
        btn_close.clicked.connect(self._close_selected_ticket)
        btn_refresh.clicked.connect(self._refresh_parking_list)
        btn_row.addWidget(btn_issue)
        btn_row.addWidget(btn_close)
        btn_row.addWidget(btn_refresh)

        self.parking_list = QListWidget()
        self.parking_stats = QLabel()
        self.parking_stats.setTextInteractionFlags(self.parking_stats.textInteractionFlags())

        layout.addWidget(form_box)
        layout.addLayout(btn_row)
        layout.addWidget(self.parking_stats)
        layout.addWidget(self.parking_list)
        return root

    def _build_settings_tab(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)

        caps = self.db.get_capacities()
        box = QGroupBox("Вместимость парковки")
        form = QFormLayout(box)
        self.emp_places = QSpinBox()
        self.emp_places.setRange(0, 10_000)
        self.emp_places.setValue(caps.employee_parking)
        self.guest_places = QSpinBox()
        self.guest_places.setRange(0, 10_000)
        self.guest_places.setValue(caps.guest_parking)
        form.addRow("Мест для сотрудников", self.emp_places)
        form.addRow("Мест для гостей", self.guest_places)

        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self._save_caps)

        layout.addWidget(box)
        layout.addWidget(btn_save)
        layout.addStretch(1)
        return root

    def _employee_in(self) -> None:
        try:
            card = validate_card_number(self.emp_card.text())
            first = validate_name(self.emp_first.text(), "Имя")
            last = validate_name(self.emp_last.text(), "Фамилия")
        except ValueError as e:
            self._error(str(e))
            return

        if self.db.get_open_visit("employee", card) is not None:
            self._error("У сотрудника уже есть активный вход. Сначала зарегистрируйте выход.")
            return

        self.db.open_employee_visit(card, first, last)
        self._info("Вход сотрудника зарегистрирован.")

    def _employee_out(self) -> None:
        try:
            card = validate_card_number(self.emp_card.text())
        except ValueError as e:
            self._error(str(e))
            return

        if not self.db.close_employee_visit(card):
            self._error("Не найден активный вход для этого пропуска.")
            return

        self._info("Выход сотрудника зарегистрирован.")

    def _guest_in(self) -> None:
        try:
            pass_id = validate_card_number(self.guest_pass.text())
            first = validate_name(self.guest_first.text(), "Имя")
            last = validate_name(self.guest_last.text(), "Фамилия")
            hours = validate_positive_int(self.guest_hours.text(), "Часы действия", max_value=72)
        except ValueError as e:
            self._error(str(e))
            return

        if self.db.get_open_visit("guest", pass_id) is not None:
            self._error("У гостя уже есть активный вход. Сначала зарегистрируйте выход.")
            return

        self.db.open_guest_visit(pass_id, first, last, hours)
        self._info("Вход гостя зарегистрирован (временный пропуск создан).")

    def _guest_out(self) -> None:
        try:
            pass_id = validate_card_number(self.guest_pass.text())
        except ValueError as e:
            self._error(str(e))
            return

        if not self.db.close_guest_visit(pass_id):
            self._error("Не найден активный вход для этого временного пропуска.")
            return

        self._info("Выход гостя зарегистрирован.")

    def _check_guest_overstays(self) -> None:
        overstays = self.db.list_open_guest_overstays()
        if not overstays:
            return

        lines = []
        for row in overstays:
            lines.append(
                f"Гость {row['first_name']} {row['last_name']} (пропуск {row['card_number']}) "
                f"просрочил пребывание. Попросите обратиться к старшему сотруднику охранной службы."
            )
        QMessageBox.warning(self, "Просроченные гостевые пропуска", "\n".join(lines))

    def _save_caps(self) -> None:
        caps = Capacities(employee_parking=int(self.emp_places.value()), guest_parking=int(self.guest_places.value()))
        self.db.set_capacities(caps)
        self._refresh_parking_list()
        self._info("Настройки сохранены.")

    def _issue_ticket(self) -> None:
        person_type = self.park_type.text().strip().lower()
        if person_type not in {"employee", "guest"}:
            self._error("Тип должен быть employee или guest.")
            return

        try:
            plate = validate_plate(self.park_plate.text())
        except ValueError as e:
            self._error(str(e))
            return

        card_number = self.park_card.text().strip() or None
        if person_type == "employee":
            if card_number is None:
                self._error("Для сотрудника требуется номер пропуска.")
                return
            try:
                card_number = validate_card_number(card_number)
            except ValueError as e:
                self._error(str(e))
                return
        else:
            if card_number is not None:
                try:
                    card_number = validate_card_number(card_number)
                except ValueError as e:
                    self._error(str(e))
                    return

        capacities = self.db.get_capacities()
        counts = self.db.parking_open_counts()

        employee_limit = capacities.employee_parking
        guest_limit = capacities.guest_parking

        if person_type == "employee":
            if counts["employee"] < employee_limit:
                self.db.issue_parking_ticket("employee", card_number, plate)
            else:
                # employees may use free guest spots if employees > guests is irrelevant;
                # main rule: employee can use unused guest places.
                if counts["guest"] < guest_limit:
                    self.db.issue_parking_ticket("employee", card_number, plate)
                else:
                    self._error("Нет свободных мест (сотрудники заняли свои и гостевые места).")
                    return
        else:
            if counts["guest"] < guest_limit:
                self.db.issue_parking_ticket("guest", card_number, plate)
            else:
                # If guests exceed employees -> suggest wait/another day.
                if counts["employee"] < employee_limit:
                    self._error("Гостевых мест нет. Предложение: подождать, пока освободится место.")
                else:
                    self._error("Мест нет. Предложение: приехать в другой день.")
                return

        self._refresh_parking_list()
        self._info("Талон выдан.")

    def _refresh_parking_list(self) -> None:
        self.parking_list.clear()
        caps = self.db.get_capacities()
        counts = self.db.parking_open_counts()
        total_used = counts["employee"] + counts["guest"]
        total_capacity = caps.employee_parking + caps.guest_parking
        self.parking_stats.setText(
            f"Занято: сотрудников {counts['employee']}/{caps.employee_parking}, "
            f"гостей {counts['guest']}/{caps.guest_parking}. "
            f"Всего: {total_used}/{total_capacity}"
        )

        for row in self.db.list_open_parking():
            text = f"#{row['id']} {row['person_type']} plate={row['car_plate']} card={row['card_number'] or '-'} issued={row['issued_at']}"
            item = QListWidgetItem(text)
            item.setData(256, int(row["id"]))
            self.parking_list.addItem(item)

    def _close_selected_ticket(self) -> None:
        item = self.parking_list.currentItem()
        if item is None:
            self._error("Выберите талон в списке.")
            return
        ticket_id = int(item.data(256))
        if not self.db.close_parking_ticket(ticket_id):
            self._error("Не удалось закрыть талон (возможно, уже закрыт).")
            return
        self._refresh_parking_list()
        self._info("Талон закрыт.")


def run_app(db_path: Path) -> int:
    app = QApplication([])
    db = Database(db_path)
    db.init_schema()
    win = MainWindow(db, base_dir=db_path.parent)
    win.show()
    try:
        return app.exec()
    finally:
        db.close()

