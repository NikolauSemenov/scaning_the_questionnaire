import json
import os
import sys
from multiprocessing import freeze_support

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.Qt import QT_VERSION_STR

from main.app.procces_validation import Data_Validation
from main.app.read_paths import changes_cache, check_cache, create_paths, check_path_json_and_tesseract, count_survey_for_validation
from main.app.scanner_survey import Scanner
import main.logging_app.logging_programm as logging_programm
from main.GUI.interface_program import Ui_MainWindow
from main.GUI.interface_show_img import PhotoViewer

PROGRAMM_NAME = "Paper Answer Scanner"
VERSION = '0.0.1'
TEST_BUILD = False
NO_STREAMS_REDIRECT = True


class XStream(QtCore.QObject):
    _stdout = None
    _stderr = None
    messageWritten = QtCore.pyqtSignal(str)

    def flush(self):
        pass

    def fileno(self):
        return -1

    def write(self, msg):
        if not self.signalsBlocked():
            self.messageWritten.emit(msg)

    @staticmethod
    def stdout():
        if not XStream._stdout:
            XStream._stdout = XStream()
            sys.stdout = XStream._stdout
        return XStream._stdout

    @staticmethod
    def stderr():
        if not XStream._stderr:
            XStream._stderr = XStream()
            sys.stderr = XStream._stderr
        return XStream._stderr


class TestMainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self)
        self.setupUi(self)

        self.process_images_thread = None  # Создаем экземпляр класса 
        self.wd_start_programm()  # Вызов первого виджета
        # Создаем окно для просмотра анкеты при валидации
        self.box_img_show = PhotoViewer(self.box_img)
        VBlayout = QtWidgets.QVBoxLayout(self.box_img)
        VBlayout.addWidget(self.box_img_show)

        self.directory = None
        self.next_answer_true = False
        self.prew_answer_true = False
        self.check_null_path = True
        self.bt_continue_survey = True
        self.qt_input_number_survey = False
        self.the_end = False
        self.get_comment = None
        self.skin_button_activ = False
        self.flag_show_error = False

        # Инициализируем все кнопки
        self.button_for_img.clicked.connect(self.open_img)
        self.button_for_json.clicked.connect(self.open_json)
        self.button_for_tesseract.clicked.connect(self.open_tesseract)
        self.button_start_dirr.clicked.connect(self.preprocces)
        self.button_cancel_dirr.clicked.connect(self.bt_cancel)
        self.button_back_dirr.clicked.connect(self.bt_back)
        self.button_for_json_valid.clicked.connect(self.open_json_for_valid)
        self.button_start_valid.clicked.connect(self.wd_validat)
        self.button_back_dirr_2.clicked.connect(self.bt_back)
        self.button_exit_path_for_valid.clicked.connect(self.bt_cancel)
        self.btn_statistika_back.clicked.connect(self.wd_start_programm)

        self.setWindowFlags(QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowCloseButtonHint)


        # Инициализируем логгер
        self.logging_start = logging_programm.logging_app(os.getlogin())
        self.my_logger = self.logging_start.get_logger("Paper_Answer_Scanner_OMR")

        # Показывает версию программы в виджетах 
        version_string = '{} *TEST BUILD* {} Qt{} Python{} '.format(PROGRAMM_NAME, VERSION, QT_VERSION_STR,
                                                                    sys.version) if TEST_BUILD \
            else '{} {}'.format(PROGRAMM_NAME, VERSION)
        self.setWindowTitle(version_string)

        # Активации вывода принтов в лого при распозновании 
        if not NO_STREAMS_REDIRECT:
            XStream.stdout().messageWritten.connect(self.handle_console_output)
            XStream.stderr().messageWritten.connect(self.handle_console_output)

    def center_widget(self):
        """
        Центрирует виджет относительно размера монитора
        """
        qtRectangle = self.frameGeometry()
        centerPoint = QtWidgets.QDesktopWidget().availableGeometry().center()
        qtRectangle.moveCenter(centerPoint)
        self.move(qtRectangle.topLeft())

    def closeEvent(self, event):
        """
        Выход при нажатии на крестик.
        """
        self.center_widget
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        # msg.setIconPixmap(pixmap)  # Своя картинка
        # msg.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        msg.setWindowTitle("Выход")
        msg.setText("Вы действительно хотите выйти?")
        # msg.setInformativeText("InformativeText")

        okButton = msg.addButton('Выход', QtWidgets.QMessageBox.AcceptRole)
        msg.addButton('Отмена', QtWidgets.QMessageBox.RejectRole)

        msg.exec()
        if msg.clickedButton() == okButton:
            event.accept()
        else:
            event.ignore()


    def show_error_img(self):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)

        msg.setWindowTitle("Ошибка")
        msg.setText("У одной из анкет потерялся скан со страницей.\nПроверьте папку с изображениями.")
        okButton = msg.addButton('Выход', QtWidgets.QMessageBox.AcceptRole)

        msg.exec()
        if msg.clickedButton() == okButton:
            sys.exit(0)
        

    def old_path(self):
        """
        Получает сохраненные ранее пути при повторном запуске
        """
        try:
            with open('paths.json', encoding='utf-8') as fg:
                path_json = json.load(fg)

            self.input_dirr_img.clear()
            self.input_dirr_img.appendPlainText(path_json['path_imgs'])

            self.input_dirr_json.clear()
            self.input_dirr_json.appendPlainText(path_json['path_json'])

            self.input_dirr_tesseract.clear()
            self.input_dirr_tesseract.appendPlainText(path_json['path_tesseract'])
        except:
            self.my_logger.exception("Не найден файл на этапе распознования'paths.json'.")
            create_paths()

    def get_path(self, mask):
        """
        Функция получает путь из input widget
        """
        self.textEdit = mask
        path = self.textEdit.toPlainText()
        return path

    def messagebox(self, path_json, path_tesseract):
        """
        Функция вызывает всплывающее окно с надписью 
        о не найденности соответствующей папки.
        Добавляет input widget и кнопку для ввода соответствующего пути
        """
        if path_json is False and path_tesseract is False:
            text = "Не найдены файлы использующиеся по умолчанию,\nпожалуйста, введите их вручную."
            self.resize(600, 330)
            self.input_dirr_json.show()
            self.button_for_json.show()
            self.text_dir_for_json.show()
            self.bt_info_json.show()

            self.text_for_tesseract.show()
            self.bt_info_tesseract.show()
            self.input_dirr_tesseract.show()
            self.button_for_tesseract.show()

            self.button_start_dirr.move(502, 280)
            self.button_cancel_dirr.move(395, 280)
            self.button_back_dirr.move(0, 280)



        elif path_json is False:
            text = "Не найден файл с шаблонной разметкой анкеты\nпожалуйста, введите путь вручную"
            self.resize(600, 270)
            self.input_dirr_json.show()
            self.button_for_json.show()
            self.text_for_tesseract.show()
            self.bt_info_tesseract.show()

            self.bt_info_tesseract.setToolTip('Указывается путь до шаблонного json файла.\nВ котором хронятся вопросы и ответы для анкеты.')
            self.text_for_tesseract.setText('Укажите путь к json файлу')
            self.button_for_json.move(500, 153)
            self.input_dirr_json.move(0, 153)
            # self.bt_info_tesseract.move(0, 158)

            self.button_start_dirr.move(502, 200)
            self.button_cancel_dirr.move(400, 200)
            self.button_back_dirr.move(0, 200)

        elif path_tesseract is False:
            self.resize(600, 270)
            self.text_for_tesseract.show()
            self.bt_info_tesseract.show()
            self.input_dirr_tesseract.show()
            self.button_for_tesseract.show()

            self.button_start_dirr.move(502, 200)
            self.button_cancel_dirr.move(400, 200)
            self.button_back_dirr.move(0, 200)
            text = "Не найден файл tesseract.exe,\nпожалуйста, введите путь вручную"

        reply = QtWidgets.QMessageBox.question(self, 'Не найден путь',
                                               text,
                                               QtWidgets.QMessageBox.Ok)
        if reply == QtWidgets.QMessageBox.Ok:
            QtWidgets.qApp.quit


    # Виджеты
    def wd_start_programm(self):
        """
        Стартовый виджет для выбора режима
        """

        self.input_dirr_json_valid.setPlainText('')
        self.box_logo.setPlainText('')

        self.setWindowIcon(QtGui.QIcon(':/ico/2.png'))
        self.wd_get_path_for_valid.hide()
        self.resize(600, 320)
        self.wd_validation.hide()
        self.wd_proccesing.hide()
        self.wd_statistika.hide()
        self.wgt_add_directories.hide()
        self.wd_statistica_for_validation.hide()
        self.center_widget()
        self.wd_warning.show()

        self.button_valid.setToolTip("В данном режиме проводится подтверждение \nответов на вопросы в спорных моментах.")
        self.button_proccesing.setToolTip("В данном режиме проводится анализ отсканированных анкет \nи сохранение в виде файла, для поздней верификации данных.")

        self.button_valid.clicked.connect(self.wd_get_path_for_validat)
        self.button_proccesing.clicked.connect(self.wd_get_paths_folders)


    def wd_get_paths_folders(self):
        """
        Виджет для получения директорий
        """

        self.wd_statistica_for_validation.hide()
        self.wd_get_path_for_valid.hide()
        self.resize(600, 210)
        self.wgt_add_directories.show()
        self.wd_validation.hide()
        self.wd_proccesing.hide()
        self.wd_statistika.hide()
        self.wd_warning.hide()
        self.center_widget()
        self.old_path()

        # Скрывает дополнительные пути
        self.text_dir_for_json.hide()
        self.bt_info_json.hide()
        self.input_dirr_json.hide()
        self.button_for_json.hide()

        self.text_for_tesseract.hide()
        self.bt_info_tesseract.hide()
        self.input_dirr_tesseract.hide()
        self.button_for_tesseract.hide()

        # Поднимаем кнопки вверх
        self.button_start_dirr.move(500, 150)
        self.button_cancel_dirr.move(390, 150)
        self.button_back_dirr.move(0, 150)

        self.bt_info_survey.setToolTip("Указывается путь до папки,в которой находятся отсканированные анкеты.")
        self.bt_info_json.setToolTip("Указывается путь до шаблонного json файла, в котором находятся вопросы, ответы  и координаты чекбоксов анкеты.")
        self.bt_info_tesseract.setToolTip("Указывается путь до программы tesseract.exe, служащая для считывания номеров анкет.")

    def preprocces(self):
        """
        Данная функция проверяет валидность путей.
        """
        flag_json = True
        flag_tess = True
        path_imgs = self.get_path(self.input_dirr_img)
        path_json_input = self.get_path(self.input_dirr_json)
        path_tesseract_input = self.get_path(self.input_dirr_tesseract)

        if path_json_input != "":
            path_json = path_json_input
            flag_json = False
        if path_tesseract_input != "":
            path_tesseract = path_tesseract_input
            flag_tess = False

        if flag_json:
            # Проверяем наличие json в дефолтных путях
            path_json = check_path_json_and_tesseract("//SAMBA/share/OBRABOTKA/LungScreen/appData/config/sample_json/survey1.json")
        
        if flag_tess:
            # Проверяем наличие tesseract в дефолтных путях
            path_tesseract = check_path_json_and_tesseract("C:/Program Files/Tesseract-OCR/tesseract.exe")

        # Если пути оба валидные, то спускаемся ниже
        if path_json is not False and path_tesseract is not False:

            if path_imgs != "":
                # Сохраняем пути
                create_paths(path_imgs, path_json, path_tesseract)
                self.wd_procces(path_imgs, path_json, path_tesseract)
            else:
                reply = QtWidgets.QMessageBox.question(self, 'Не указан путь с анкетами',
                                                       "Введите, пожалуйста, путь до папки с отсканированными анкетами.",
                                                       QtWidgets.QMessageBox.Ok)
                if reply == QtWidgets.QMessageBox.Ok:
                    QtWidgets.qApp.quit
                else:
                    pass
        else:
            self.messagebox(path_json, path_tesseract)

    def wd_procces(self, path_imgs, path_json, path_tesseract):
        """
        Виджет распознования анкет
        """
        self.wd_get_path_for_valid.hide()
        self.wd_proccesing.show()
        self.resize(600, 420)
        self.wd_validation.hide()
        self.wgt_add_directories.hide()
        self.wd_statistica_for_validation.hide()
        self.center_widget()

        self.button_continue.setDisabled(True)  # Делаем кнопку неактивной
        self.button_continue.setStyleSheet("background: #006400;")
        self.button_cancel_procces.clicked.connect(self.bt_cancel_procces)
        self.button_continue.clicked.connect(self.wd_statistic_for_proces)

        self.process_images_thread = Scanner(path_imgs, path_json, path_tesseract, self)
        self.process_images_thread.started.connect(self.on_started)
        self.process_images_thread.finished.connect(self.on_finished)
        self.process_images_thread.progress_pbar.connect(
            self.on_change, QtCore.Qt.QueuedConnection)
        self.process_images_thread.start()

    def wd_statistic_for_proces(self):
        """
        Виджет для статистики по распознованию анкет
        """
        self.wd_get_path_for_valid.hide()
        self.resize(300, 230)
        self.wd_proccesing.hide()
        self.wd_validation.hide()
        self.wd_statistika.show()
        self.wgt_add_directories.hide()
        self.wd_statistica_for_validation.hide()
        self.center_widget()

        self.btn_statistika_continue.clicked.connect(self.wd_validat)
        self.btn_statistika_exit.clicked.connect(self.bt_cancel)
        self.btn_statistika_back.clicked.connect(self.wd_start_programm)

    def wd_get_path_for_validat(self):
        """
        Виджет для получения пути заполненного json для валидации
        """
        try:
            self.wd_get_path_for_valid.show()
            self.wd_proccesing.hide()
            self.wd_statistika.hide()
            self.wd_warning.hide()
            self.wd_validation.hide()
            self.wd_statistica_for_validation.hide()
            self.label_21.hide()
            self.input_info_for_validation.hide()
            self.resize(600, 195)
            self.center_widget()



            path_cache, _, _ = check_cache()
            if path_cache is not None:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Information)

                msg.setWindowTitle("Не завершенная сессия")
                msg.setText("Имеется не законченная верификация анкеты\nУчтите, при отмене не законченная анкета удалится из папки validation")

                okButton = msg.addButton('Удалить', QtWidgets.QMessageBox.AcceptRole)
                msg.addButton('Продолжить', QtWidgets.QMessageBox.RejectRole)

                msg.exec()
                if msg.clickedButton() != okButton:
                    self.input_dirr_json_valid.appendPlainText(path_cache)
                    self.wd_validat()
                else:
                    os.remove(path_cache)
                    changes_cache()
                    QtWidgets.qApp.quit
        except:
            self.my_logger.exception("Удален кеш перед верификации!!!!!!!.")

    def wd_validat(self):
        """
        Виджет для подтверждения ответов анкет
        """
        path_json = self.input_dirr_json_valid.toPlainText()
        if path_json != '':
            self.lb_comment.hide()
            self.label_22.hide()
            self.wd_get_path_for_valid.hide()
            self.wd_proccesing.hide()
            self.wd_statistika.hide()
            self.wd_warning.hide()
            self.wd_statistica_for_validation.hide()
            self.wd_validation.show()
            self.resize(600, 730)
            self.center_widget()

            self.process_images_thread = Data_Validation(path_json, self)
            self.process_images_thread.started.connect(self.started_valid)
            self.process_images_thread.finished.connect(self.finished_valid)
            self.process_images_thread.mysignal.connect(self.get_img, QtCore.Qt.QueuedConnection)
            self.process_images_thread.start()

            self.button_ok_procces.clicked.connect(self.bt_next_question)
            self.button_continue_valid.clicked.connect(self.bt_prev_question)
            self.button_continue_survey.clicked.connect(self.bt_pass_survey)
            self.button_new_number_survey.clicked.connect(self.bt_input_new_number_survey)

        else:
            reply = QtWidgets.QMessageBox.question(self, 'Указаны не все пути',
                                                   "Введите, пожалуйста, все пути.",
                                                   QtWidgets.QMessageBox.Ok)
            if reply == QtWidgets.QMessageBox.Ok:
                QtWidgets.qApp.quit
            else:
                pass

    def wd_statistic_for_validation(self):
        """
        Виджет со статистикой по валидации
        """
        self.wd_get_path_for_valid.hide()
        self.wd_proccesing.hide()
        self.wd_statistika.hide()
        self.wd_warning.hide()
        self.wd_validation.hide()
        self.wd_statistica_for_validation.show()
        self.resize(600, 220)
        self.center_widget()

        self.button_exit.clicked.connect(self.bt_cancel)

    def handle_console_output(self, text):
        """
        Лог процесса распознования
        """
        self.box_logo.moveCursor(QtGui.QTextCursor.End)
        self.box_logo.insertPlainText(text)

    # Папка и файлы для загрузки в программу
    def open_img(self):
        """
        Загрузка папки с анкетами для wd_get_paths_folders
        """
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку")
        if directory:
            self.input_dirr_img.clear()
            self.input_dirr_img.appendPlainText(directory)
        else:
            pass

    def open_json(self):
        """
        Загрузка файла с шаблонным json для wd_get_paths_folders
        """
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Выберите json файл с шаблоном анкеты', '',
                                                            'Json (*.json)', options=options)
        if fileName:
            self.input_dirr_json.clear()
            self.input_dirr_json.appendPlainText(fileName)
        else:
            pass

    def open_tesseract(self):
        """
        Загрузка файла для wd_get_paths_folders
        """
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Укажите путь до файла tessetact', '',
                                                            '(*.exe)', options=options)
        if fileName:
            self.input_dirr_tesseract.clear()
            self.input_dirr_tesseract.appendPlainText(fileName)
        else:
            pass

    def open_json_for_valid(self):
        """
        Загрузка файла с заполенным json для валидации
        """
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Выберите json файл, с распознаными анкетами', '',
                                                            'Json (*.json)', options=options)
        if fileName:
            self.input_dirr_json_valid.clear()
            self.input_dirr_json_valid.appendPlainText(fileName)

            # проверяем наличие этого файла в папке validation
            name_file = os.path.basename(fileName)
            # path_check = os.path.exists('//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey/validation/' + name_file)
            path_check = os.path.exists("result_survey/validation/" + name_file)

            try:
                _, count_false = count_survey_for_validation(fileName)
                if count_false == 0:
                    self.label_21.show()
                    self.input_info_for_validation.hide()
                    self.bt_info_message("Не нуждается в верификации")
                    self.label_21.hide()
                    self.button_start_valid.setDisabled(True)
                    self.button_start_valid.setStyleSheet("background: #006400;")


                elif path_check:
                    self.label_21.show()
                    self.input_info_for_validation.hide()
                    self.bt_info_message("Файл уже был верифицирован")
                    self.button_start_valid.setDisabled(False)
                    self.button_start_valid.setStyleSheet("""
                                                            QPushButton{
                                                            border-radius: 5px;
                                                            background: rgb(128,191,62);
                                                            color:#000000;
                                                            border: 1px #DADADA solid;
                                                            }
                                                            QPushButton:hover{
                                                             background: #006400;
                                                             border: 1px #C6C6C6 solid;
                                                             }""")
                else:
                    self.button_start_valid.setDisabled(False)
                    self.button_start_valid.setStyleSheet("""
                                                            QPushButton{
                                                            border-radius: 5px;
                                                            background: rgb(128,191,62);
                                                            color:#000000;
                                                            border: 1px #DADADA solid;
                                                            }
                                                            QPushButton:hover{
                                                             background: #006400;
                                                             border: 1px #C6C6C6 solid;
                                                             }""")
                    self.label_21.setText('Необходимо верифицировать:')
                    self.label_21.show()
                    self.input_info_for_validation.show()
                    self.input_info_for_validation.setText(str(count_false)+' анкет.')
            except:
                self.label_21.show()
                self.label_21.setText('Выбран не тот файл.')
        else:
            pass

    # Кнопки
    def bt_back(self):
        """
        Переход в стартовый виджет
        """
        self.wd_warning.show()
        self.wd_start_programm()

    def bt_cancel(self):
        """
        Кнопка для выхода из программы
        """
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        # msg.setIconPixmap(pixmap)  # Своя картинка

        msg.setWindowTitle("Выход")
        msg.setText("Вы действительно хотите выйти?")
        # msg.setInformativeText("InformativeText")

        okButton = msg.addButton('Да', QtWidgets.QMessageBox.AcceptRole)
        msg.addButton('Нет', QtWidgets.QMessageBox.RejectRole)

        msg.exec()
        if msg.clickedButton() == okButton:
            sys.exit(0)
        else:
            QtWidgets.qApp.quit

    def on_started(self):
        """
        Старт потока для распознования
        """
        print('Началась обработка изображений.')
        if self.flag_show_error:
            self.show_error_img()

    def on_finished(self):
        """
        Завершает поток для распознования
        """
        print("Обработка закончилась.")
        self.button_continue.setDisabled(False)  # Делаем кнопку для перехода активной
        self.button_cancel_procces.hide()  # Для выхода делаем не активной
        self.button_cancel_procces.setStyleSheet("background: #006400;")
        self.button_continue.setStyleSheet("background: rgb(128,191,62);")

        self.button_continue.setStyleSheet("""
                                    QPushButton:hover{
                                    background: #006400;
                                    border: 1px #C6C6C6 solid;
                                    }""")
    def on_change(self, progress):
        """
        Прогресс выполнения для распознования
        """
        self.pbar_file_progress.setValue(progress)

    def bt_cancel_procces(self):
        """
        Кнопка для выхода из распознования
        """
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        # msg.setIconPixmap(pixmap)  # Своя картинка

        msg.setWindowTitle("Вы действительно хотите выйти?")
        msg.setText("Все изменения не будут сохранены.")
        # msg.setInformativeText("InformativeText")

        okButton = msg.addButton('Да', QtWidgets.QMessageBox.AcceptRole)
        msg.addButton('Нет', QtWidgets.QMessageBox.RejectRole)

        msg.exec()
        if msg.clickedButton() == okButton:
            sys.exit(0)
        else:
            QtWidgets.qApp.quit

    def bt_info_message(self, text):
        """
        Кнопка для выхода из распознования
        """
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)

        msg.setWindowTitle("Предуреждение")
        msg.setText(text)
        # msg.setInformativeText("InformativeText")

        okButton = msg.addButton('Ок', QtWidgets.QMessageBox.AcceptRole)

        msg.exec()
        if msg.clickedButton() == okButton:
            # sys.exit(0)
            QtWidgets.qApp.quit
        # else:
        #     QtWidgets.qApp.quit

    def started_valid(self):
        """
        Старт потока для валидации
        """
        pass

    def finished_valid(self):
        """
        Завершение потока для валидации
        """
        if self.the_end is not False:
            self.wd_statistic_for_validation()  # При завршении валидции переход к статистики

    def get_img(self, s):
        """
        Получение изображения для валидации
        """
        image = QtGui.QImage(s)
        self.box_img_show.setPhoto(QtGui.QPixmap.fromImage(image))

    def bt_next_question(self):
        """
        Переход к следующему вопросу в валидации
        """
        self.next_answer_true = True
        if self.skin_button_activ is not False:
            self.button_ok_procces.setStyleSheet("background-color:#52cc00;\n""")

        else:
            self.button_ok_procces.setStyleSheet("background-color:#d3d3d3;\n""")

    def bt_prev_question(self):
        """
        Переход к предыдущему вопросу в валидации
        """
        self.prew_answer_true = True
        self.button_ok_procces.setStyleSheet("background-color:#d3d3d3; border:0.3px solid gray;\n""")

    def bt_input_new_number_survey(self):
        """
        Кнопка для появления ввода номера анкеты
        """
        self.qt_input_number_survey = True

    def bt_pass_survey(self):
        """
        Кнопка для пропуска анкеты в валидации
        """

        text, ok = QtWidgets.QInputDialog.getText(self, 'Информация', 'Укажите причину пропуска анкеты:')

        if ok and text != '':
            self.get_comment = text
            self.next_answer_true = True
            self.prew_answer_true = True
            self.bt_continue_survey = False
        else:
            pass

def main ():
    freeze_support()
    app = QtWidgets.QApplication(sys.argv)
    # app.setStyle(QtWidgets.QStyleFactory.create('Fusion'))
    app.setStyleSheet(open("style/style.qss").read())

    form = TestMainWindow(app)
    form.show()
    sys.exit(app.exec_())
