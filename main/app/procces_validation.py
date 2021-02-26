import json
import os

from PyQt5 import QtCore, QtWidgets

from main.app.read_paths import changes_cache, count_survey_for_validation, check_next_survey, check_cache
import main.logging_app.logging_programm as logging_programm


class Data_Validation(QtCore.QThread):
    mysignal = QtCore.pyqtSignal(str)

    def __init__(self, path_json, parent=None):
        super(Data_Validation, self).__init__(parent)
        self.parent = parent
        self.path_json = path_json

        self.logging_start = logging_programm.logging_app(os.getlogin())
        self.my_logger = self.logging_start.get_logger("Paper_Answer_Scanner_OMR")
        

    def skip_next_survey(self, skip_survey):

        if skip_survey:
            self.parent.bt_continue_survey = True
        else:
            self.parent.next_answer_true = False
    
    def get_survey(self):

        # Подгружаем json файл и считаем количество не валидированных анкет
        surveys, need_valid = count_survey_for_validation(self.path_json)

        # Проверяем на досрочное закрытие программы.
        _, count_survey, cahe_need_valid_survey = check_cache()

        if count_survey is not None and cahe_need_valid_survey is not None:
            survey_true = count_survey
            need_valid = cahe_need_valid_survey
        else:
            survey_true = 1

        return surveys, need_valid, survey_true

    def check_comment_survey(self, comment):

        if comment is not None:
            self.parent.lb_comment.setText(comment)
            self.parent.lb_comment.show()
            self.parent.label_22.show()
        else:
            self.parent.lb_comment.hide()
            self.parent.label_22.hide()

    def show_number_survey(self, page_number, number_survey, valid_number_survey):

        if page_number == 1:
            # Передаем номер анкеты в интерфейс
            self.parent.lb_number_answer_show.setText(str(number_survey))

            if valid_number_survey is False:
                # Если номер анкеты не валидный, просим ввести вручную
                self.parent.text_for_input_number_answer.show()
                self.parent.qp_inpunt_number_answer.show()

                self.parent.label_10.hide()
                self.parent.lb_number_answer_show.hide()
                self.parent.button_new_number_survey.hide()

            else:
                # Либо показываем номер анкеты с возможностью исправления путём кнопки
                self.parent.text_for_input_number_answer.hide()
                self.parent.qp_inpunt_number_answer.hide()

                self.parent.label_10.show()
                self.parent.lb_number_answer_show.show()
                self.parent.button_new_number_survey.show()
        else:
            # При обратной стороне анкеты взаимодействие с номером анкеты отключаем
            self.parent.label_10.hide()
            self.parent.lb_number_answer_show.hide()
            self.parent.button_new_number_survey.hide()
            self.parent.text_for_input_number_answer.hide()
            self.parent.qp_inpunt_number_answer.hide()


    def set_directory(self, directory):
        # Передаем путь к изображению 
        self.mysignal.emit(directory)
    
    def get_list_index_survey_for_validation(self, questions, valid_number_survey):

        unvalid_index_questions = []
        # Собираем вопросы требующие валидацию
        for i, question in enumerate(questions):

            if not question['valid']:
                unvalid_index_questions.append(i)

        if len(unvalid_index_questions) == 1:  # Если один вопрос
            self.parent.button_ok_procces.setStyleSheet("background-color:#FF0033;\n""")


        # Если нет вопросов требующие валидацию и номер анкеты true
        if len(unvalid_index_questions) == 0 and valid_number_survey is True:
            flag_done = False
        else:
            flag_done = True
        
        return unvalid_index_questions, flag_done

    def check_question(self, unvalid_index_questions, index):

        # Если нет вопросов для валидации, но необходимо исправить номер анкеты
        # Добавляем один элемент в массив, чтобы сделать равными index и  unvalid_index_questions - 1
        if len(unvalid_index_questions) == 0:
            unvalid_index_questions.append(1)
            # Скрываем всё лишнее
            self.parent.label_19.hide()
            self.parent.input_number_question.hide()
            self.parent.button_continue_survey.hide()

            self.parent.label_22.show()
            self.parent.lb_comment.setText("Только номер анкеты.")
            self.parent.lb_comment.show()
        else:
            self.parent.label_19.show()
            self.parent.input_number_question.show()
            self.parent.button_continue_survey.show()

        if index != len(unvalid_index_questions) - 1:
            self.parent.button_ok_procces.setText('Следующий вопрос')
            self.parent.button_ok_procces.setStyleSheet("""
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
            self.parent.input_number_question.setText(
                str(index + 1) + '/' + str(len(unvalid_index_questions)))

            if index + 1 == len(unvalid_index_questions) - 1:
                self.parent.skin_button_activ = True
        else:
            self.parent.skin_button_activ = False
            self.parent.button_ok_procces.setText('Подтвердить сторону')
            self.parent.button_ok_procces.setStyleSheet("""
                                        QPushButton{
                                        border-radius: 5px;
                                        background: #FF0000;
                                        color:#000000;
                                        border: 1px #DADADA solid;
                                    }
                                        QPushButton:hover{
                                         background: #8B0000;
                                         border: 1px #C6C6C6 solid;
                                         }""")
            self.parent.input_number_question.setText(
                str(index + 1) + '/' + str(len(unvalid_index_questions)))

        if index == 0:
            self.parent.button_continue_valid.hide()
        else:
            self.parent.button_continue_valid.show()

    def wait_click_button(self):

        while not self.parent.next_answer_true and not self.parent.prew_answer_true:
            if self.parent.qt_input_number_survey is not False:
                self.parent.text_for_input_number_answer.show()
                self.parent.qp_inpunt_number_answer.show()
            continue

    def update_number_survey(self):

        # Как только пользователь нажал на кнопку обновляем номер анкеты и скрывает ввод
        input_new_number_survey = self.parent.qp_inpunt_number_answer.toPlainText()
        if input_new_number_survey != '':
            self.parent.lb_number_answer_show.setText(str(input_new_number_survey))
            self.parent.qp_inpunt_number_answer.hide()
            self.parent.text_for_input_number_answer.hide()

            self.parent.label_10.show()
            self.parent.lb_number_answer_show.show()
            self.parent.button_new_number_survey.show()

    def skin_button_continue(self, index, unvalid_index_questions):

        if index + 1 == len(unvalid_index_questions) - 1:
            self.parent.skin_button_activ = True
        else:
            self.parent.skin_button_activ = False
    
    def shape_survey(self, survey, question):

        survey['validation'] = True
        if self.parent.bt_continue_survey is not False:
            number_survey = self.parent.qp_inpunt_number_answer.toPlainText()
            if number_survey != '':
                survey['number_survey'] = number_survey
                survey['valid_number_survey'] = True

            # Собираем ответы данные пользователем в список
            checked_items = []
            for index_checkbox in range(self.parent.ql_widget.count()):
                if self.parent.ql_widget.item(index_checkbox).checkState() == QtCore.Qt.Checked:
                    value = self.parent.ql_widget.item(index_checkbox).text()
                    checked_items.append(value)
                else:
                    question['valid'] = True

            list_1 = []
            # Расстановка True/False относительно ответов
            for checkbox_value in checked_items:
                for j, _ in enumerate(question['answers']):
                    answer_text = question['answers'][j]['answer_text']
                    if checkbox_value == answer_text:
                        question['answers'][j]['answer'] = True
                        question['valid'] = True
                        list_1.append(checkbox_value)
                    elif checkbox_value != answer_text and answer_text not in list_1:
                        question['answers'][j]['answer'] = False
        else:
            survey['validation'] = False
            survey['comment'] = self.parent.get_comment
            self.parent.bt_continue_survey = True
            return True

        return False
    
    def record_data_in_json(self, surveys):
        
        # path = '//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey/validation/' + os.path.basename(self.path_json)
        path = 'result_survey/validation/' + os.path.basename(self.path_json)
        # Сохраняем каждый раз, при подтверждении стороны анкеты
        with open(path, 'w', encoding='utf-8') as outfile:
            json.dump(surveys, outfile, indent=2, ensure_ascii=False, separators=(',', ': '))
        
        return path

    
    def data_for_statistica(self, need_valid, survey_true, survey_pass):
        """
        Функция для передачи данных для статистики по валидации
        """

        self.parent.input_survey_for_valid.setText(str(need_valid))
        self.parent.survey_check.setText(str(survey_true - survey_pass - 1))
        self.parent.survey_pass.setText(str(survey_pass))

    def check_folder_try(self):
        """
        Данная функция проверяет существует ли папка validation
        Если нет, то содает
        """
        # path = "//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey/validation"
        path = "result_survey/validation"
        check = os.path.exists(path)
        if check is False:
            # os.mkdir("//SAMBA/share/OBRABOTKA/LungScreen/appData/result_survey/validation")
            os.mkdir("result_survey/validation")
        else:
            pass

    def sort_survey_for_export(self, survey, path):
        """
        Данная функция сортирует выходной файл для экспорта.
        """
        try_rec = 0
        questions = {}
        list_surveys = []
        count = 0
        for i in range(len(survey)):
            try_rec += 1
            if survey[i]['page_number'] == 1:
                number_survey = survey[i]['number_survey']
                questions["number_survey"] = number_survey
                questions["questions"] = []

            for question in survey[i]['questions']:
                questions_text = question['question_text']
                questions["questions"].append({
                    "question_text": questions_text,
                    "answers": []
                })
                for j, _ in enumerate(question['answers']):
                    answer_bool = question['answers'][j]['answer']
                    answer_text = question['answers'][j]['answer_text']

                    questions["questions"][count]["answers"].append({
                        "answers_text": answer_text,
                        "answer": answer_bool})
                count += 1

            # Добавлять в список, лишь когда обработаются обе стороны анкеты
            if try_rec % 2 == 0:
                a = {**{}, **questions}
                list_surveys.append(a)
                questions = {}
                count = 0
            else:
                count = len(survey[i]['questions'])

        # Ставим в имени файла тег valid
        os.rename(self.path_json, f"result_survey/procesing/{os.path.basename(self.path_json).split('.')[0]}_valid.json")
        path_record = f"result_survey/validation/{os.path.basename(path).split('.')[0]}_valid.json"
        os.remove(path)

        with open(path_record, 'w', encoding='utf-8') as outfile:
            json.dump(list_surveys, outfile, indent=2, ensure_ascii=False, separators=(',', ': '))

    def run(self):
        """
        Функция для валидирования данных анкет путём интерфеса программы
        """

        # Проверяем наличие папки
        self.check_folder_try()

        # Подгружаем анкеты
        surveys, need_valid, survey_true = self.get_survey()

        count = 0
        survey_pass = 0  # Счётчик пропуска анкет
        skip_survey = False

        for index_survey, survey in enumerate(surveys):

            if survey['validation'] is False or survey['validation'] is None:
                count += 1

                # На случай пропуска первой страницы анкеты
                self.skip_next_survey(skip_survey)

                # Передаем данные в интерфейс программы.
                self.parent.input_number_survey.setText(str(survey_true) + '/' + str(need_valid))
                self.check_comment_survey(survey['comment'])
                self.set_directory(survey['directory'])
                self.show_number_survey(survey['page_number'], survey['number_survey'], survey['valid_number_survey'])
                
                unvalid_index_questions, flag_done = self.get_list_index_survey_for_validation(survey['questions'], survey['valid_number_survey'])
                                                                                                  
                index = 0
                # Если есть вопросы для валидации
                while flag_done:
                    try:
                        question = survey['questions'][unvalid_index_questions[index]]
                        questions_text = question['question_text']

                        for i, _ in enumerate(question['answers']):
                            answer_text = question['answers'][i]['answer_text']
                            self.parent.question.setText(questions_text)

                            # Динамически добавляем чекбоксы
                            item = QtWidgets.QListWidgetItem(answer_text)
                            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                            item.setCheckState(QtCore.Qt.Unchecked)
                            self.parent.ql_widget.addItem(item)
                    except:
                        pass
                    
                    # if survey["page_number"] == 1:
                    self.check_question(unvalid_index_questions, index)

                    # Ждём пока пользователь нажмёт на кнопку
                    self.wait_click_button()
                    self.update_number_survey()
                    self.parent.qt_input_number_survey = False
                    
                    # Переход к следующему вопросу, либо вернуться к предыдущему
                    if self.parent.next_answer_true:

                        if index != len(unvalid_index_questions) - 1:
                            index += 1
                        else:
                            flag_done = False

                    elif self.parent.prew_answer_true:
                        if index != 0:
                            index -= 1

                    self.skin_button_continue(index, unvalid_index_questions)

                    # Вносим изменения в анкету
                    if self.shape_survey(survey, question):
                        # Если нажали пропустить анкету
                        next_number_survey_1 = check_next_survey(index_survey, surveys)

                        # Если пропускается первая страница, то автоматически пропускается 2 стр.
                        if survey['number_survey'] == next_number_survey_1:
                            skip_survey = True

                        survey_pass += 1
                        flag_done = False
                        continue

                    # Очищаем данные от анкеты
                    self.parent.question.clear()
                    self.parent.ql_widget.clear()
                    self.parent.qp_inpunt_number_answer.clear()

                    self.parent.next_answer_true = False
                    self.parent.prew_answer_true = False
            else:
                continue  # Если анкета не нужндающаяся в валидации

            # Проверяем какая сторона анкеты идет следующей (для счётчика на виджете)
            next_number_survey = check_next_survey(index_survey, surveys)

            # Проверяем следующую сторону с привязкой к number_survey
            if survey['number_survey'] != next_number_survey:
                survey_true += 1
            # Последняя страница
            elif next_number_survey is False:
                survey_true += 1

            self.parent.skin_button_activ = False

            path = self.record_data_in_json(surveys)
            # Добавляем путь в кеш, для непредвиденного выхода
            changes_cache(path, survey_true, need_valid)

            self.parent.button_ok_procces.setText('Следующий вопрос')
            self.parent.button_new_number_survey.hide()
            self.parent.lb_comment.hide()
            self.parent.label_22.hide()

        # Передаем данные для статистики по валидации    
        self.data_for_statistica(need_valid, survey_true, survey_pass)
        self.parent.the_end = True

        # По окончании валидации, удаляем путь из кеша
        changes_cache(None, None, None)

        # По окончании валидации, сортируем файл для экспорта
        self.sort_survey_for_export(surveys, path)
