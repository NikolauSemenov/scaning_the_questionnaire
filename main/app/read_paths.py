import json
import os

import main.logging_app.logging_programm as logging_programm

logging_start = logging_programm.logging_app(os.getlogin())
my_logger = logging_start.get_logger("Paper_Answer_Scanner_OMR")


def create_paths(path_imgs=None, path_json=None, path_tesseract=None):
    """
    Создает файл с путями для кэша.
    """
    paths_json = {"path_json_for_validation": None,
                  "count_survey": None, 'path_imgs': path_imgs, 'path_json': path_json,
                  'path_tesseract': path_tesseract, 'need_valid_survey' : None}

    with open(f'paths.json', 'w', encoding='utf-8') as outfile:
        json.dump(paths_json, outfile, indent=2, ensure_ascii=False, separators=(',', ': '))


def changes_cache(rec_in_json=None, count_survey=None, need_valid = None):
    """
    Сохраняем, на случай досрочного закрытия программы и продолжения выполнения в другое время
    """

    path_json = load_json('paths.json')

    path_json['path_json_for_validation'] = rec_in_json
    path_json['count_survey'] = count_survey
    path_json['need_valid_survey'] = need_valid

    with open('paths.json', 'w', encoding='utf-8') as outfile:
        json.dump(path_json, outfile, indent=2,ensure_ascii=False, separators=(',', ': '))



def check_cache():
    """
    Проверяет, было ли досрочное закрытие программы в режиме валидации.
    """
    try:
        json_file = load_json('paths.json')
    except:
        my_logger.exception("Удален кеш перед верификации.")
        create_paths()
        json_file = load_json('paths.json')

    count_survey = json_file['count_survey']
    path_json = json_file['path_json_for_validation']
    need_valid = json_file['need_valid_survey']

    return path_json, count_survey, need_valid



def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def count_survey_for_validation(json_for_valid):
    """
    Функция считывает сколько необходимо валидировать анкет
    """
    data_json = load_json(json_for_valid)

    count_survey, i = 0, 0
    for _ in data_json:
        try:
            if data_json[i]['validation'] == False:
                next_survey = check_next_survey(i, data_json)
                if data_json[i]['number_survey'] == next_survey:
                    # Если последующий элемент равен предыдущему,то пропускаем последующий
                    count_survey += 1
                    i+=1
                # Если последний элемент в списке
                elif next_survey is False:
                    count_survey += 1
                    break
                else:
                    # Значит элемент уникален
                    count_survey += 1
            i+=1
        except:
            break

    return data_json, count_survey


def check_path_json_and_tesseract(path_file):
    """
    Данная функция проверяет наличие файла по данной директории.
    """
    check_file = os.path.exists(path_file)

    if check_file is True:
        return path_file
    else:
        # Возвращает false
        return check_file


def check_next_survey(index_survey, surveys):
    """
    Проверяет следующую страницу анкеты.
    """
    try:
        i = 1
        while True:
            number_survey = surveys[index_survey+i]['number_survey']

            if surveys[index_survey+i]['validation'] == False:
                return number_survey
            else:
                i += 1
    except:
        return False
