import datetime
import fnmatch
import json
import os
import cv2
import numpy as np
import pytesseract
from PyQt5 import QtCore
from pyzbar.pyzbar import decode

from main.app.read_paths import count_survey_for_validation
import main.logging_app.logging_programm as logging_programm


def find_files_by_mask(path: str) -> [list, int, bool]:
    """
    Данная функция перебирает директорию с изображениями,
    фильтрует по маске(jpg).
    Возвращает список с путями до изображений.
    """
    flag = False
    list_dirr_to_imgs = []
    for dir_path, _, filename in os.walk(path):
        for el in filename:
            if fnmatch.fnmatch(el, "*.jpg"):
                filepath = os.path.join(dir_path, el)
                list_dirr_to_imgs.append(filepath)

                if el.split('.')[0] == 'img_1':
                    flag = True

    sort_list = sorted(list_dirr_to_imgs, key=lambda x: len(x))
    return sort_list, len(sort_list), flag


class Scanner(QtCore.QThread):
    """
    Данный класс обрабатывает изображение анкеты.
    Вначале накладываются на изображение фильтры, для лучшего распознования.
    Далее на изображении распознаются 4 qr кода и декодируются,
    для обрезки изображения по координатам центра четырёх qr кода.
    После этого считывается номер анкеты на первой страницы в виде строки,
    после распознаёт все чекбоксы анкеты и выводит анкету в электронном формате.
    """

    progress_pbar = QtCore.pyqtSignal(int)

    def __init__(self, path_imgs=None, path_json=None, path_tesseract=None, parent=None):
        super(Scanner, self).__init__(parent)
        self.img = None
        self.img_for_number_survey = None
        self.path_imgs = path_imgs
        self.path_json = path_json
        self.path_tesseract = path_tesseract
        self.name_img = None
        self.number_page = None
        self.parent = parent
        self.qr_codes = {'00': 0, '01': 0, '10': 0, '11': 0}
        self.logging_start = logging_programm.logging_app(os.getlogin())
        self.my_logger = self.logging_start.get_logger("Paper_Answer_Scanner_OMR")

    def load_img(self, path_file: str) -> np.ndarray:
        """
        На входе данной функции подается путь до изображения.
        Возвращает загруженное изображение.
        """
        self.name_img = path_file.split('\\')[1]

        if path_file is not None:
            self.img = cv2.imread(path_file)
            if self.img is None:
                return None
            else:
                return self.img
    
    def get_json(self, path_json):
        """
        Данная функция возвращает загруженный json файл.
        """
        with open(path_json, encoding='utf-8') as json_file:
            return json.load(json_file)

    def full_transformations(self) -> np.ndarray:
        """
        Данная функция применяет 3 фильтра к изображению,
        после обрезает изображение по центрам 4 qr кода.
        Возвращает обрезанное изображение 1000х1000px.
        """
        img = self.img
        if img is not None:
            try:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                img = cv2.GaussianBlur(img, (3, 3), 0)

                img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 77, 10)
                self.img_for_number_survey = self.perspective_transform(img, 1000, 1000)

                img = self.perspective_transform(img, 1000, 1000)
            except:
                self.my_logger.exception("Не удалось предобработать изображение.")
                return None
            else:
                self.img = img
                return img
        else:
            return None

    def perspective_transform(self, img: np.ndarray, x: int, y: int) -> np.ndarray:
        """
        Подфункция full_transformations(), которая обрезает изображение по qr кодам.
        Возвращает 1000х1000px изображение.
        """

        codes = decode(img)

        if len(codes) != 4:
            img = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
            codes = decode(img)

            if len(codes) != 4:
                print(f"Error, обнаружено лишь {len(codes)} qr в изображении {self.name_img}")
                qr_values = json.loads(codes[0].data)
                self.number_page = qr_values['page_number']
                return None

        for code in codes:
            qr_values = json.loads(code.data)
            w = code.rect[2] / 2
            h = code.rect[3] / 2
            left = code.rect[0]
            top = code.rect[1]
            self.number_page = qr_values['page_number']
            if (qr_values['x'] == 0) and (qr_values['y'] == 1):
                self.qr_codes['01'] = (left + w, top + h)
            if (qr_values['x'] == 1) and (qr_values['y'] == 1):
                self.qr_codes["11"] = (left + w, top + h)
            if (qr_values['x'] == 1) and (qr_values['y'] == 0):
                self.qr_codes["10"] = (left + w, top + h)
            if (qr_values['x'] == 0) and (qr_values['y'] == 0):
                self.qr_codes["00"] = (left + w, top + h)

        src_pts = np.array([(self.qr_codes['10'][0], self.qr_codes['10'][1]),
                            (self.qr_codes['11'][0], self.qr_codes['11'][1]),
                            (self.qr_codes['01'][0], self.qr_codes['01'][1]),
                            (self.qr_codes['00'][0], self.qr_codes['00'][1])
                            ], dtype=np.float32)

        dst_pts = np.array([[0, 0], [x, 0], [x, y], [0, y]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        box_img = cv2.warpPerspective(img, M, (x, y))
        img = cv2.rotate(box_img, cv2.ROTATE_90_CLOCKWISE)

        self.img = img
        return img

    def check_survey(self, number_survey: str, number_survey_for_2_page: str) -> list:
        """
        Функция, проверяющая значения всех чекбоксов на заданной странице
        на основании заданого шаблона.
        Возвращает заполненный шаблон.
        """

        img = self.img
        load_survey = self.get_json(self.path_json)

        if self.number_page == 1:
            survey = load_survey[0]
            survey['number_survey'] = number_survey
        else:
            survey = load_survey[1]
            survey['number_survey'] = number_survey_for_2_page

        for question in survey['questions']:
            for answer in question['answers']:
                position = answer["answer_position"]
                answer["answer"] = self.check_position(self.number_page,
                                                       img, position["x"], position["y"])
        return survey

    def check_position(self, page_number: int, transform_img: np.ndarray, x: int, y: int) -> bool:
        """
        Функция для проверки checkbox'a на наличии в нём ответа на вопрос.
        Возвращает True(ответ был дан), False(нет ответа).
        """
        h, w = 12, 16

        testbox = np.zeros(shape=[13, 18], dtype=np.uint8)
        testbox = cv2.rectangle(testbox, (0, 0), (16, 13), 255, thickness=1)
        testbox = cv2.rectangle(testbox, (1, 0), (17, 12), 255, thickness=1)

        box = transform_img[y - h:y + h, x - w:x + w]
        checkbox, binar_img = self.selection_checkbox(box)

        if checkbox is False:
            print(f'{self.name_img} не распознан чекбокс, качество распознавания снижена.')
            avg_color = np.average(binar_img)

            if avg_color >= 30:
                return True
            else:
                return False
        else:
            test_box = self.image_hash(testbox)
            test_img = self.image_hash(checkbox)
            test_hesh = self.compare_hash(test_box, test_img)

        if test_hesh >= 5:
            return True
        else:
            return False

    def selection_checkbox(self, image: np.ndarray) -> [np.ndarray, np.ndarray]:
        """
        Данная функция вырезает чекбокс из предполагаемой области.
        На выходе получаем изображение с чекбоксом.
        """
        threshold_max_area = 210
        threshold_min_area = 150

        binar_img = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        contours = cv2.findContours(binar_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours[0] if len(contours) == 2 else contours[1]

        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.035 * peri, True)
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h)
            area = cv2.contourArea(c)
            i = 1
            if len(approx) == 4 or (threshold_max_area > area > threshold_min_area) or (1 <= aspect_ratio <= 2):
                if w >= 13 and h >= 10:
                    checkbox_thresh = binar_img[y:y + h, x:x + w]
                    cv2.rectangle(checkbox_thresh, (0, 0), (w - 1, h - 1), (255, 255, 255), 1)
                    i += 1
                else:
                    checkbox_thresh = False
            else:
                checkbox_thresh = False
            if i > 1:
                break

        return checkbox_thresh, binar_img

    def image_hash(self, image: np.ndarray) -> str:
        """
        Функция, считающая хеш изображения.
        На выходе получается бинарная строка из чисел.
        """
        if image is False:
            pass
        resized = cv2.resize(image, (8, 8), interpolation=cv2.INTER_AREA)
        avg = resized.mean()
        _, threshold_image = cv2.threshold(
            resized, avg, 255, 0)

        hash_img = ""
        for x in range(8):
            for y in range(8):
                val = threshold_image[x, y]
                if val == 255:
                    hash_img = hash_img + "1"
                else:
                    hash_img = hash_img + "0"
        return hash_img

    def compare_hash(self, hash_box: str, hash_img_box: str) -> int:
        """
        Данная функция сравнивает хеш эталонного чекбокса и проверяемого.
        Возвращает количество несовпадений.
        """
        i, count = 0, 0
        while i < len(hash_box):
            if hash_box[i] != hash_img_box[i]:
                count += 1
            i += 1
        return count

    def validation_survey(self, survey: list, path_file) -> bool:
        """
        Данная функция проверяет заполненность анкеты.
        """

        for questions in survey['questions']:
            count_true = 0
            count_false = 0

            survey['directory'] = path_file

            if survey['number_survey'] is None and self.number_page == 1:
                survey['valid_number_survey'] = False
                survey['validation'] = False
            else:
                survey['valid_number_survey'] = True

            for i, _ in enumerate(questions['answers']):
                question = questions['question_text']
                answer = questions['answers'][i]['answer']
                if question != 'Имели ли Вы постоянный профессиональный контакт:' and question != 'Отмечается ли у Вас один из симптомов?':
                    if question != 'Имеются ли у Вас хронические заболевания?' and question != 'В течение последнего года выполнялась ли Вам рентгеновское исследование легких?':
                        if answer == True:
                            count_true += 1
                            if count_true > 1:
                                questions['valid'] = False
                                survey['validation'] = False
                                print(f'{self.name_img} Найдено ответов больше допустимого.')

                if answer == True:
                    count_false += 1
            if question != "Сколько сигарет в день Вы выкуриваете?" and question != "Сколько лет вы курите?":
                if count_false == 0:
                    survey['validation'] = False
                    questions['valid'] = False
                    print(f'{self.name_img} На вопрос не был дан ответ.')

        if survey['validation'] is False:
            return False
        else:
            return True

    def convert_img_to_text(self) -> str:
        """
        Данная функция распознает номер анкеты на первой странице.
        Возвращает номер анкеты в виде строки.
        """
        pytesseract.pytesseract.tesseract_cmd = self.path_tesseract

        try:
            thresh = cv2.threshold(self.img_for_number_survey, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            img_text = self.img_for_number_survey[75:125, 761:990]
            img_text_t = thresh[75:125, 761:990]

            contours = cv2.findContours(img_text_t, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            contours = contours[0] if len(contours) == 2 else contours[1]

            filtered_contours = []
            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.035 * peri, True)
                x, y, w, h = cv2.boundingRect(approx)
                area = cv2.contourArea(c)
                if area > 15:
                    filtered_contours.append(c)
            cnts = np.concatenate(filtered_contours)
            x, y, w, h = cv2.boundingRect(cnts)
            checkbox_thresh = img_text_t[y - 2: y + h + 2, x - 3: x + w + 3]

            text = pytesseract.image_to_string(checkbox_thresh, config='--psm 8 -c tessedit_char_whitelist=0123456789abcdef')

            number_survey = text.replace('\n\f', '')

        except:
            return None
        else:
            return number_survey

    def add_error_survey(self, path_error_survey:str) -> list:
        """
        Данная функция добавляет не распозанную анкету для ручного заполнения
        С соответствующим комментарием
        """
        json_load = self.get_json(self.path_json)

        if self.number_page == 1:
            survey = json_load[0]
        else:
            survey = json_load[1]

        for question in survey['questions']:
            survey['directory'] = path_error_survey
            survey['validation'] = False
            survey['comment'] = 'Нуждается в заполнении'
            question['valid'] = False
            survey['valid_number_survey'] = False
            for answer in question['answers']:
                answer["answer"] = False

        return survey


    def check_path_try(self) -> None:
        """
        Проверяем на существование папки procesing
        Если нет такой папки, создаём
        """
        # path = "//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey/procesing"
        path = "result_survey/procesing"
        check = os.path.exists(path)
        if check is False:
            # os.mkdir("//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey")
            # os.mkdir("//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey/procesing")
            os.mkdir("result_survey")
            os.mkdir("result_survey/procesing")


    def set_data_wd_statistica(self, path_survey:str, count_error_survey:int, length_list:int, error_number_survey:int) -> None:
        """
        Функция для передач данных для статистики по распознованию
        """
        _, need_valid = count_survey_for_validation(path_survey)

        self.parent.qlabel_full_survey.setText(f'{int(length_list / 2)}')
        self.parent.qlabel_error_number_survey.setText(str(error_number_survey))
        self.parent.qlabel_need_valid.setText(str(need_valid))


    def record_in_json(self, survey: list, need_valid: int) -> str:
        """
        Функция, записывающая выходные данные в json файл.
        """
        now = datetime.datetime.now()
        # path = f'//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey/procesing/{os.environ.get("USERNAME")}_{now.day}-{now.month}-{now.year}_{now.hour}_{now.minute}.json'
        path = f'result_survey/procesing/{os.environ.get("USERNAME")}_{now.day}-{now.month}-{now.year}_{now.hour}_{now.minute}.json'
        self.check_path_try()
        self.parent.input_dirr_json_valid.appendPlainText(path)

        with open(path, "w", encoding='utf-8') as config_file:
            json.dump(survey, config_file, indent=2, ensure_ascii=False, separators=(',', ': '))

        if need_valid == 0:  # Если нет анкет для валидации, сохранять в обе папки
            with open(path, "w", encoding='utf-8') as config_file:
                json.dump(survey, config_file, indent=2, ensure_ascii=False, separators=(',', ': '))

        return path


    def zero_up(self, sort_list:list, path:str) -> None:
        for i, j in zip(sort_list, range(1, len(sort_list), 2)):
            os.rename(i, f'{path}/img_{j}.jpg')

    def up_zero(self, sort_list:list, path:str) -> None:
        a = int(len(sort_list) / 2)
        for i, j in zip(sort_list[a:], range(len(sort_list), 1, -2)):
            os.rename(i, f'{path}/img_{j}.jpg')
        

    def check_length_list(self, length_list:int )-> bool:
        """
        Проверяет валидность папки с анкетами.
        """
        if length_list == 0:
            print('Изображений не найдено.')
            self.parent.check_null_path = False

        elif length_list % 2 != 0:
            self.parent.flag_show_error = True
            return True
        return False
    

    def rename_and_sort_img_survey(self, flag:bool, list_path_img:list) -> list:
        """
        Переименовывает сканы с анкетами и сортирует их в папке.
        """
        if flag is False:
            print("Сортировка изображений")
            self.zero_up(list_path_img, self.path_imgs)
            self.up_zero(list_path_img, self.path_imgs)
            list_path_img, _, _ = find_files_by_mask(self.path_imgs)
            print("Сортировка изображений закончена.")
            return list_path_img
        return None


    def get_number_survey(self) -> str:
        """
        Возвращает номер анкеты.
        """
        number_survey = self.convert_img_to_text()
        if number_survey is None or len(number_survey) != 8:
            print(f"{self.name_img} Не удалось распознать номер анкеты.")
            return None
        else:
            return number_survey


    def run(self):
        """
        Функция для взаимодействия с классом Scanner
        """
        # Обнуеляем полосу загрузки.
        self.progress_pbar.emit(0)

        # Подгружаем файлы и фильтруем по маске изображения с анкетами.
        list_path_img, length_list, flag = find_files_by_mask(self.path_imgs)

        # Проверяем количество анкет на четность и не != 0.
        if self.check_length_list(length_list):
            return None        

        # Переименовываем и сортируем анкеты в папке(если необходимо).
        sort_imgs = self.rename_and_sort_img_survey(flag, list_path_img)
        if sort_imgs is not None:
            list_path_img = sort_imgs

        list_surves = []
        count_survey, count_error_survey, need_valid = 0, 0, 0
        error_number_survey = 0
        number_survey_for_2_page = None

        for path_file in list_path_img:
            number_survey = None
            if self.load_img(path_file) is None:
                print(f"{self.name_img} Не удалось загрузить изображение")
                count_survey += 1
                count_error_survey += 1
                continue

            tran_img: np.ndarray = self.full_transformations()
            if tran_img is None:
                print(f"{self.name_img} Не удалось преобразовать изображения")
                count_survey += 1
                count_error_survey += 1

                # Записываем директорию не валидных анакет, для ручной верификации
                error_survey = self.add_error_survey(path_file)
                list_surves.append(error_survey)
                number_survey_for_2_page = None
                continue

            if self.number_page != 2:
                number_survey = self.get_number_survey()
                number_survey_for_2_page = number_survey
                if number_survey is None:
                    error_number_survey += 1

            survey = self.check_survey(number_survey, number_survey_for_2_page)
            if self.validation_survey(survey, path_file) is False:
                need_valid += 1

            # Заполняем полосу загрузки.
            count_survey += 1
            progress = count_survey / length_list * 100
            self.progress_pbar.emit(progress)

            list_surves.append(survey)

        # Запись данных для валидации
        record_path_json = self.record_in_json(list_surves, need_valid)

        # Передаем данные для wd_statistica
        self.set_data_wd_statistica(record_path_json, count_error_survey, length_list, error_number_survey)
