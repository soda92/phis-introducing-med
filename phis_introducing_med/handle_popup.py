from kapybara.shared_data import shared_data
from kapybara.shortcuts import TimeoutException, WebDriverWait, By, EC as ec
from kapybara import FormElement
import time

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


def handle_post_save_popups(driver, yes_option):
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

