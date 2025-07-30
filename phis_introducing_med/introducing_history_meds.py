from kapybara import WebDriverWait, By, EC as ec
from kapybara.shortcuts import TimeoutException
import time
from datetime import datetime
from .is_drug_name_similar import is_drug_name_similar
from .extract_med_data import extract_medication_data
import re

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

            if is_drug_name_similar(drug_name, clicked_drugs):
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

