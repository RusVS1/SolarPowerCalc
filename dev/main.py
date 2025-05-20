from parser import parse_weather
from calc import calc_power
import pandas as pd
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QCheckBox, QFormLayout, QPushButton, QLabel, QFrame,
    QSpacerItem, QSizePolicy, QComboBox, QFileDialog, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QDoubleValidator, QMovie
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class Worker(QObject):
    finished = pyqtSignal()
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    warning_occurred = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        while True:
            try:
                df = parse_weather()
                if df is None:
                    self.warning_occurred.emit("Ошибка при получении данных о погоде. Повтор...")
                    continue

                efficiency = self.params['efficiency']
                length = self.params['length']
                width = self.params['width']
                default_position = self.params['default_position']
                azimuth = self.params['azimuth']
                tilt = self.params['tilt']

                power_df = calc_power(
                    df=df,
                    KPD=efficiency / 100,
                    LENGHT=length,
                    WIDTH=width,
                    optim=default_position,
                    beta=tilt,
                    y=azimuth
                )

                if power_df is None:
                    self.warning_occurred.emit("Ошибка парсинга. Повтор...")
                    continue

                self.result_ready.emit(power_df)
                break

            except Exception as e:
                self.warning_occurred.emit(f"Ошибка парсинга. Повтор...")
                continue

        self.finished.emit()

class SolarPanelForm(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Калькулятор выработки солнечной панели")
        self.resize(800, 400)
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()
        form_container = QVBoxLayout()
        form_layout = QFormLayout()

        double_validator = QDoubleValidator()
        double_validator.setNotation(QDoubleValidator.StandardNotation)
        double_validator.setDecimals(2)

        self.efficiency_input = QLineEdit()
        self.length_input = QLineEdit()
        self.width_input = QLineEdit()
        self.azimuth_input = QLineEdit()
        self.tilt_input = QLineEdit()

        for field in [self.efficiency_input, self.length_input,
                    self.width_input, self.azimuth_input, self.tilt_input]:
            field.setValidator(double_validator)

        form_layout.addRow("КПД (%)", self.efficiency_input)
        form_layout.addRow("Длина (м)", self.length_input)
        form_layout.addRow("Ширина (м)", self.width_input)

        self.default_position_checkbox = QCheckBox("Оптимальное положение")
        self.default_position_checkbox.stateChanged.connect(self.toggle_azimuth_tilt)
        form_layout.addRow("", self.default_position_checkbox)

        form_layout.addRow("Азимут (°)", self.azimuth_input)
        form_layout.addRow("Наклон (°)", self.tilt_input)

        form_container.addLayout(form_layout)

        self.export_button = QPushButton("Выгрузить данные")
        self.export_button.setVisible(False)
        form_container.addWidget(self.export_button, alignment=Qt.AlignRight)
        self.export_button.clicked.connect(self.export_to_csv)

        self.calculate_button = QPushButton("Рассчитать")
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red;")
        form_container.addWidget(self.warning_label)
        self.calculate_button.clicked.connect(self.show_loading_animation)
        form_container.addWidget(self.calculate_button)

        main_layout.addLayout(form_container)

        self.graph_area = QFrame()
        self.graph_area.setFrameShape(QFrame.StyledPanel)
        self.graph_area.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.graph_area.setFixedWidth(400)
        self.graph_area.setMinimumHeight(300)
        self.graph_area.setMaximumHeight(500)
        self.graph_area.setStyleSheet("background-color: #f0f0f0;")

        self.day_selector = QComboBox()
        self.day_selector.currentIndexChanged.connect(self.plot_wel_for_selected_day)

        self.day_selector.setStyleSheet("""
            QComboBox {
                background-color: #f0f0f0;
                color: black;
            }
            QComboBox::item {
                background-color: #f0f0f0;
                color: black;
            }
            QComboBox::item:selected {
                background-color: lightblue;
                color: black;
            }
        """)

        self.loading_label = QLabel()
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setFixedSize(100, 100)

        gif_path = os.path.abspath("spinner.gif")
        self.movie = QMovie(gif_path)
        self.movie.setScaledSize(QSize(100, 100))
        self.loading_label.setMovie(self.movie)
        self.loading_label.setVisible(False)

        self.figure = Figure()
        self.figure.patch.set_facecolor('#f0f0f0')
        self.canvas = FigureCanvas(self.figure)

        self.graph_layout = QVBoxLayout()
        self.graph_layout.addWidget(self.day_selector)
        self.graph_layout.addWidget(self.loading_label, alignment=Qt.AlignCenter)
        self.graph_layout.addWidget(self.canvas)

        self.graph_area.setLayout(self.graph_layout)
        main_layout.addWidget(self.graph_area)

        self.setLayout(main_layout)

    def toggle_azimuth_tilt(self, state):
        if state == Qt.Checked:
            self.azimuth_input.clear()
            self.tilt_input.clear()
            self.azimuth_input.setDisabled(True)
            self.tilt_input.setDisabled(True)

            self.azimuth_input.setStyleSheet("")
            self.tilt_input.setStyleSheet("")
        else:
            self.azimuth_input.setDisabled(False)
            self.tilt_input.setDisabled(False)

    def show_loading_animation(self):
        if not self.validate_inputs():
            self.warning_label.setText("Заполните все поля.")
            return

        self.warning_label.setText("")

        self.day_selector.clear()
        self.export_button.setVisible(False)

        self.canvas.setVisible(False)
        self.loading_label.setVisible(True)
        self.movie.jumpToFrame(0)
        self.movie.start()

        params = self.get_panel_parameters()
        if not params:
            self.warning_label.setText("Ошибка ввода данных.")
            self.hide_loading_animation()
            return

        self.thread = QThread()
        self.worker = Worker(params)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.result_ready.connect(self.handle_parse_result)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.warning_occurred.connect(self.handle_warning)
        self.thread.finished.connect(self.hide_loading_animation)

        self.thread.start()

    def handle_error(self, message):
        self.warning_label.setText(f"Ошибка: {message}")
    
    def handle_warning(self, message):
        self.warning_label.setText(message)

    def hide_loading_animation(self):
        self.movie.stop()
        self.loading_label.setVisible(False)
        self.canvas.setVisible(True)

    def validate_inputs(self):
        fields = [
            self.efficiency_input,
            self.length_input,
            self.width_input
        ]

        if not self.default_position_checkbox.isChecked():
            fields.extend([self.azimuth_input, self.tilt_input])

        all_filled = True
        for field in fields:
            if not field.text().strip():
                field.setStyleSheet("border: 2px solid red;")
                all_filled = False
            else:
                field.setStyleSheet("")

        return all_filled
    
    def get_panel_parameters(self):
        try:
            efficiency = float(self.efficiency_input.text())
            length = float(self.length_input.text())
            width = float(self.width_input.text())
            default_position = self.default_position_checkbox.isChecked()

            if default_position:
                azimuth = None
                tilt = None
            else:
                azimuth = float(self.azimuth_input.text())
                tilt = float(self.tilt_input.text())

            return {
                'efficiency': efficiency,
                'length': length,
                'width': width,
                'default_position': default_position,
                'azimuth': azimuth,
                'tilt': tilt
            }
        except ValueError:
            return None
        
    def plot_wel_for_selected_day(self):
        selected_index = self.day_selector.currentIndex()
        if selected_index < 0 or not hasattr(self, 'power_df'):
            return

        selected_day = self.unique_days[selected_index]
        df_day = self.power_df[self.power_df['datetime'].dt.date == selected_day]

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        ax.plot(df_day['datetime'], df_day['Wel'], marker='o', linestyle='-')
        ax.set_ylabel("кВт*ч")
        ax.grid(True)

        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H:%M'))

        for label in ax.get_xticklabels():
            label.set_rotation(45)
        ax.margins(x=0)

        self.canvas.draw()
    
    def handle_parse_result(self, power_df):
        self.power_df = power_df

        power_df['datetime'] = pd.to_datetime(
            power_df['YEAR'].astype(str) + '-' +
            power_df['MO'].astype(str) + '-' +
            power_df['DY'].astype(str) + ' ' +
            power_df['HR'].astype(str) + ':00'
        )

        self.unique_days = sorted(power_df['datetime'].dt.date.unique())

        self.day_selector.clear()
        for day in self.unique_days:
            self.day_selector.addItem(day.strftime("%Y-%m-%d"))

        self.plot_wel_for_selected_day()

        self.export_button.setVisible(True)

    def export_to_csv(self):
        if not hasattr(self, 'power_df'):
            self.warning_label.setText("Нет данных для выгрузки.")
            return

        default_filename = "выработка_энергии.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить файл как",
            default_filename,
            "CSV файлы (*.csv);;Все файлы (*)"
        )

        if not file_path:
            return
        try:
            cols_to_save = ['YEAR', 'MO', 'DY', 'HR', 'Wel']
            filtered_df = self.power_df[cols_to_save]

            filtered_df.to_csv(file_path, index=False, encoding='utf-8-sig')

            self.warning_label.setText(
                f'<span style="color: green;">Файл успешно сохранён:<br>{file_path}</span>'
            )
        except Exception as e:
            self.warning_label.setText(
                f'<span style="color: red;">Ошибка сохранения: {str(e)}</span>'
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SolarPanelForm()
    window.show()
    sys.exit(app.exec_())