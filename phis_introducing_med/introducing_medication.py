import re
import time
from datetime import datetime
import csv
from pathlib import Path

import pandas as pd
from kapybara import By, ec, WebDriverWait, FormElement
from kapybara.shared_data import shared_data
from kapybara.shortcuts import TimeoutException
from phis_introducing_med.is_drug_name_similar import is_drug_name_similar

# 新增：CSV文件路径
OUTPUT_FILE = Path('./执行结果/用药记录.csv')


def extract_medication_data(rows):
    """从用药记录行中提取药品数据"""
    medications = []
    for row in rows:
        try:
            drug_name = row.find_element(By.XPATH, './td[3]/div').text
            drug_date = row.find_element(By.XPATH, './td[6]/div').text
            drug_name = drug_name.replace('（', '(').replace('）', ')').strip()
            if drug_name:
                medications.append({'name': drug_name, 'date': drug_date})
        except Exception:
            # 忽略无法提取的行
            pass
    return medications


def save_medication_records(sfzh, history_meds, outpatient_meds):
    """将收集到的用药记录保存到CSV文件"""
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        history_str = '; '.join([f'{m["name"]} ({m["date"]})' for m in history_meds])
        outpatient_str = '; '.join(
            [f'{m["name"]} ({m["date"]})' for m in outpatient_meds]
        )
        file_exists = OUTPUT_FILE.exists()
        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['身份证号', '历史用药', '门诊用药'])
            writer.writerow([sfzh, history_str, outpatient_str])
        print(f'用药记录已保存到: {OUTPUT_FILE}')
    except Exception as e:
        print(f'保存用药记录失败: {e}')


def alert_element_exist(xpath: str) -> bool:
    driver = shared_data.driver
    try:
        element = WebDriverWait(driver, 3).until(
            ec.visibility_of_element_located((By.XPATH, xpath))
        )
    except TimeoutException:
        return False
    else:
        return True


def _handle_post_save_popups(driver, yes_option):
    """
    统一处理点击“保存”后可能出现的各种弹窗。
    返回一个元组 (status, message)，其中 status 表示操作是否应该继续。
    """
    try:
        # 检查“药品名称不能为空”的弹窗
        if alert_element_exist('//span[contains(text(), "药品名称不能为空或无")]'):
            print('错误：药品列表为空，无法保存。')
            driver.find_element(By.XPATH, "//button[text()='确定']").click()
            return (False, 'empty_drug_list')

        # 检查“本季度已做过慢病随访”的弹窗
        if alert_element_exist(f"//button[text()='{yes_option}']"):
            print(f"检测到重复随访弹窗，选择：'{yes_option}'")
            FormElement(f"//button[text()='{yes_option}']").click()
            if yes_option == '否':
                return (False, 'duplicate_followup_declined')
            # 如果选择了“是”，则可能还有后续弹窗，继续检查
            time.sleep(1)  # 等待下一个弹窗出现

        # 检查“需要先保存随访”的弹窗
        if alert_element_exist('//span[contains(text(), "需要先")]'):
            print('需要先保存随访，正在确认...')
            driver.find_element(By.XPATH, '//button[contains(text(), "是")]').click()
            time.sleep(1)
            # 点击确认后的“确定”按钮
            driver.find_element(By.XPATH, "//button[text()='确定']").click()
            print('用药情况已保存。')
            # 检查并关闭“是否加入到个人服务计划中”的弹窗
            time.sleep(0.5)
            if alert_element_exist(
                '//span[contains(text(), "是否加入到个人服务计划中")]'
            ):
                driver.find_element(
                    By.XPATH, '//button[contains(text(), "否")]'
                ).click()
            return (True, 'saved_via_nested_dialog')

        # 检查通用的“确定”按钮，表示成功保存
        confirm_button = driver.find_elements(By.XPATH, "//button[text()='确定']")
        if confirm_button:
            print('用药情况已保存。')
            confirm_button[0].click()
            return (True, 'saved_successfully')

    except Exception as e:
        # 捕获意外错误，例如元素在检查后立即消失
        print(f'处理弹窗时发生未知错误: {e}')
        return (True, 'unknown_error')  # 假设操作可继续，避免卡死

    return (True, 'no_popup_found')  # 没有找到任何弹窗


"""
引入历史用药
"""


def introducing_history_medication(
    driver, drug_counter, drug_names_set, clicked_drugs, start_date, end_date
):
    # 点击加载门诊用药
    element = WebDriverWait(driver, 10).until(
        ec.presence_of_element_located(
            (By.XPATH, '//div[contains(text(), "加载门诊用药")]')
        )
    )
    driver.execute_script('arguments[0].click();', element)
    time.sleep(3.5)

    all_outpatient_meds = []  # 用于存储所有门诊用药记录
    try:
        # 等待所有匹配的元素出现
        yp = WebDriverWait(driver, 8).until(
            ec.presence_of_all_elements_located(
                (
                    By.XPATH,
                    "//div[contains(@class, 'x-grid-group ')]/div[2]/div/table/tbody/tr",
                )
            )
        )
        yp_number = len(yp)
        all_outpatient_meds = extract_medication_data(yp)  # 提取数据
    except TimeoutException:
        yp_number = 0

    if yp_number == 0:
        print('门诊用药无用药需要引入')
        element = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH, "//button[text()='选择']"))
        )
        driver.execute_script('arguments[0].click();', element)
        return clicked_drugs, all_outpatient_meds
    else:
        print('开始引入用药')
        for row in yp:
            # 如果已经引入了五个药品，停止引入
            if drug_counter >= 5:
                print('最多引入五个药品，停止引入')
                break

            drug_name = row.find_element(By.XPATH, './td[3]/div').text

            drug_name = drug_name.replace('（', '(').replace('）', ')')
            # drug_name = re.sub(r'\(.*?\)', '', drug_name).strip()

            # 提取用药日期
            drug_date_text = row.find_element(By.XPATH, './td[6]/div').text

            if drug_date_text == '':
                continue

            drug_date = datetime.strptime(drug_date_text, '%Y-%m-%d')
            # 判断随访日期是否在指定范围内
            if start_date <= drug_date <= end_date:
                pass
            else:
                continue

            if is_drug_name_similar(drug_name, clicked_drugs, threshold=0.8):
                continue
            if drug_name in drug_names_set and drug_name not in clicked_drugs:
                print('正在引入:', drug_name)

                # 点击药物
                try:
                    drug_element = WebDriverWait(driver, 5).until(
                        ec.presence_of_element_located(
                            (By.XPATH, f'//div[contains(text(), "{drug_name}")]')
                        )
                    )
                except:
                    try:
                        drug_name = drug_name.replace('(', '（').replace(')', '）')
                        drug_element = WebDriverWait(driver, 5).until(
                            ec.presence_of_element_located(
                                (By.XPATH, f'//div[contains(text(), "{drug_name}")]')
                            )
                        )
                    except:
                        drug_name = drug_name.replace('（', '(').replace('）', ')')
                        drug_name = re.sub(r'\(.*?\)', '', drug_name).strip()

                        drug_element = WebDriverWait(driver, 20).until(
                            ec.presence_of_element_located(
                                (By.XPATH, f'//div[contains(text(), "{drug_name}")]')
                            )
                        )

                # 滚动到药物元素
                driver.execute_script(
                    'arguments[0].scrollIntoView(true);', drug_element
                )
                time.sleep(1)  # 确保滚动操作完成并页面稳定

                # 尝试模拟鼠标事件
                driver.execute_script(
                    "var evt = document.createEvent('MouseEvents');"
                    "evt.initMouseEvent('mousedown', true, true, window);"
                    'arguments[0].dispatchEvent(evt);'
                    "evt.initMouseEvent('mouseup', true, true, window);"
                    'arguments[0].dispatchEvent(evt);'
                    "evt.initMouseEvent('click', true, true, window);"
                    'arguments[0].dispatchEvent(evt);',
                    drug_element,
                )
                time.sleep(1.5)
                clicked_drugs.add(drug_name)  # 将点击过的药品添加到集合中
                drug_counter += 1

        # 点击选择按钮
        element = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH, "//button[text()='选择']"))
        )
        driver.execute_script('arguments[0].click();', element)
        time.sleep(1.5)
    return clicked_drugs, all_outpatient_meds


def introducing_medication(driver, diseases_name, new_sf_data):
    # 获取本季度已做过慢病随访，是否继续保存
    with open('./执行结果/env.txt', 'r', encoding='utf-8') as file:
        content = file.readlines()
    # 使用 split() 方法分割字符串
    yes = content[5].replace('：', ':').split(':')[1].strip()
    # 新增：读取是否保存用药记录的选项
    save_records_option = '否'
    if len(content) > 9 and '是否保存用药记录' in content[9]:
        save_records_option = content[9].replace('：', ':').split(':')[1].strip()

    print('本季度已做过慢病随访，是否继续保存:', yes)

    start_date = content[7].replace('：', ':').split(':')[1].strip()
    print('引入用药起始时间:', start_date)
    end_date = content[8].replace('：', ':').split(':')[1].strip()
    print('引入用药结束时间:', end_date)

    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    start_date = datetime(start_date.year, start_date.month, start_date.day)

    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    end_date = datetime(end_date.year, end_date.month, end_date.day)

    # 读取Excel文件
    file_path = '文档/药品对照表.xlsx'

    # 根据 diseases_name 来决定读取哪个 sheet
    if '高血压' in diseases_name and '糖尿病' not in diseases_name:
        sheet_name_to_read = '高血压'
    elif '高血压' not in diseases_name and '糖尿病' in diseases_name:
        sheet_name_to_read = '糖尿病'
    elif '高血压' in diseases_name and '糖尿病' in diseases_name:
        sheet_name_to_read = '高血压糖尿病'
    else:
        sheet_name_to_read = '高血压糖尿病'

    # 读取指定的sheet
    df_selected = pd.read_excel(file_path, sheet_name=sheet_name_to_read)

    # 获取药品名称集合
    drug_names_set = set(df_selected['产品名称'])

    # 创建一个新的集合来存储替换后的药品名称
    updated_drug_names_set = set()

    # 遍历 drug_names_set 中的每个药品名称
    for drug_name in drug_names_set:
        # 替换全角括号为半角括号
        updated_drug_name = drug_name.replace('（', '(').replace('）', ')')
        # 将替换后的名称添加到新集合中
        updated_drug_names_set.add(updated_drug_name)

    drug_names_set = updated_drug_names_set

    # 判断用药元素是否加载完成
    while True:
        try:
            element = WebDriverWait(driver, 10).until(
                ec.presence_of_element_located(
                    (By.XPATH, '//div[contains(text(), "无")]')
                )
            )
            value = element.text
            if value == '无':
                print('用药情况正在引入')
                break
        except:
            pass

    clicked_drugs = set()  # 创建一个集合用于存储已经点击过的药品
    drug_counter = 0  # 引入药品计数器
    all_history_meds = []  # 用于存储所有历史用药记录

    # 点击加载历史用药
    element = WebDriverWait(driver, 10).until(
        ec.presence_of_element_located(
            (By.XPATH, '//div[contains(text(), "加载历史用药")]')
        )
    )
    driver.execute_script('arguments[0].click();', element)
    time.sleep(3.5)

    try:
        # 等待所有匹配的元素出现
        yp_groups = WebDriverWait(driver, 8).until(
            ec.presence_of_all_elements_located(
                (
                    By.XPATH,
                    "//div[contains(@class, 'x-grid-group ')]",
                )
            )
        )
        # 提取所有历史用药数据
        for group_div in yp_groups:
            rows = group_div.find_elements(
                By.XPATH, ".//table[@class='x-grid3-row-table']/tbody/tr"
            )
            all_history_meds.extend(extract_medication_data(rows))

        yp_number = len(all_history_meds)

    except TimeoutException:
        yp_number = 0

    if yp_number == 0:
        print('历史用药无用药需要引入')
        element = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH, "//button[text()='选择']"))
        )
        driver.execute_script('arguments[0].click();', element)

        clicked_drugs2, all_outpatient_meds = introducing_history_medication(
            driver, drug_counter, drug_names_set, clicked_drugs, start_date, end_date
        )

        # 点击用药的保存
        element = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH, '//*[@id="medSave"]/div/div[1]'))
        )
        driver.execute_script('arguments[0].click();', element)
        time.sleep(1.5)

        # 获取本季度已做过慢病随访，是否继续保存
        with open('./执行结果/env.txt', 'r', encoding='utf-8') as file:
            content = file.readlines()
        # 使用 split() 方法分割字符串
        yes = content[5].replace('：', ':').split(':')[1].strip()

        # 处理所有可能的弹窗
        status, message = _handle_post_save_popups(driver, yes)

        # 根据选项保存用药记录
        if save_records_option == '是':
            sfzh = new_sf_data.get('sfzh')  # 假设身份证号在 new_sf_data 中
            if sfzh:
                save_medication_records(sfzh, all_history_meds, all_outpatient_meds)
            else:
                print('警告：未找到身份证号，无法保存用药记录。')

        if not status:
            # 如果处理函数返回 False，则意味着操作应中止
            return False

        return clicked_drugs2
    else:
        print('开始引入历史用药')
        any_drug_selected = False
        group_divs = WebDriverWait(driver, 10).until(
            ec.presence_of_all_elements_located(
                (By.XPATH, "//div[contains(@class, 'x-grid-group ')]")
            )
        )
        t = True

        for group_div in group_divs:
            # 提取随访日期标题
            follow_up_title_element = group_div.find_element(
                By.XPATH, ".//div[contains(@class, 'x-grid-group-title')]"
            )
            follow_up_title_text = follow_up_title_element.text
            if '随访日期' not in follow_up_title_text:
                continue

            # 提取随访日期
            follow_up_date_text = (
                follow_up_title_text.split(':')[1].split('(')[0].strip()
            )
            follow_up_date = datetime.strptime(follow_up_date_text, '%Y-%m-%d')
            # 判断随访日期是否在指定范围内
            if start_date <= follow_up_date <= end_date:
                pass
                # print(f"随访日期 {follow_up_date_text} 在指定范围内")
            else:
                continue

            # 提取该块中的所有用药行
            rows = group_div.find_elements(
                By.XPATH, ".//table[@class='x-grid3-row-table']/tbody/tr"
            )

            for row in rows:
                drug_name = row.find_element(By.XPATH, './td[3]/div').text
                drug_name = drug_name.replace('（', '(').replace('）', ')')
                # drug_name = re.sub(r'\(.*?\)', '', drug_name).strip()

                if is_drug_name_similar(drug_name, clicked_drugs, threshold=0.8):
                    continue
                if drug_name in drug_names_set and drug_name not in clicked_drugs:
                    print('正在引入:', drug_name)

                    # 点击药物
                    try:
                        drug_element = WebDriverWait(driver, 5).until(
                            ec.presence_of_element_located(
                                (By.XPATH, f'//div[contains(text(), "{drug_name}")]')
                            )
                        )
                    except:
                        try:
                            drug_name = drug_name.replace('(', '（').replace(')', '）')
                            drug_element = WebDriverWait(driver, 5).until(
                                ec.presence_of_element_located(
                                    (
                                        By.XPATH,
                                        f'//div[contains(text(), "{drug_name}")]',
                                    )
                                )
                            )
                        except:
                            drug_name = drug_name.replace('（', '(').replace('）', ')')
                            drug_name = re.sub(r'\(.*?\)', '', drug_name).strip()

                            drug_element = WebDriverWait(driver, 20).until(
                                ec.presence_of_element_located(
                                    (
                                        By.XPATH,
                                        f'//div[contains(text(), "{drug_name}")]',
                                    )
                                )
                            )

                    # 滚动到药物元素
                    driver.execute_script(
                        'arguments[0].scrollIntoView(true);', drug_element
                    )
                    time.sleep(1)  # 确保滚动操作完成并页面稳定

                    # 尝试模拟鼠标事件
                    driver.execute_script(
                        "var evt = document.createEvent('MouseEvents');"
                        "evt.initMouseEvent('mousedown', true, true, window);"
                        'arguments[0].dispatchEvent(evt);'
                        "evt.initMouseEvent('mouseup', true, true, window);"
                        'arguments[0].dispatchEvent(evt);'
                        "evt.initMouseEvent('click', true, true, window);"
                        'arguments[0].dispatchEvent(evt);',
                        drug_element,
                    )
                    time.sleep(1.5)
                    clicked_drugs.add(drug_name)  # 将点击过的药品添加到集合中
                    any_drug_selected = True
                    drug_counter += 1
                    # 如果已经引入了五个药品，停止引入
                    if drug_counter >= 5:
                        print('最多引入五个药品，停止引入')
                        break

        # 点击选择按钮
        element = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH, "//button[text()='选择']"))
        )
        driver.execute_script('arguments[0].click();', element)
        time.sleep(1.5)

        # if drug_counter == 0:
        #     print("历史用药中没有引入任何药品,需要引入门诊用药")
        clicked_drugs2, all_outpatient_meds = introducing_history_medication(
            driver, drug_counter, drug_names_set, clicked_drugs, start_date, end_date
        )
        clicked_drugs = clicked_drugs | clicked_drugs2

        # 点击用药的保存
        element = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH, '//*[@id="medSave"]/div/div[1]'))
        )
        driver.execute_script('arguments[0].click();', element)
        time.sleep(1.5)
        # 处理所有可能的弹窗
        status, message = _handle_post_save_popups(driver, yes)

        # 根据选项保存用药记录
        if save_records_option == '是':
            sfzh = new_sf_data.get('sfzh')  # 假设身份证号在 new_sf_data 中
            if sfzh:
                save_medication_records(sfzh, all_history_meds, all_outpatient_meds)
            else:
                print('警告：未找到身份证号，无法保存用药记录。')

        if not status:
            # 如果处理函数返回 False，则意味着操作应中止
            return False
    if not any_drug_selected:
        print('没有任何药品被选中')

    return clicked_drugs
