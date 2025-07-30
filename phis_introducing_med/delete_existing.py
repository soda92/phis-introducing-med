from kapybara import WebDriverWait, By, EC as ec
from kapybara.shortcuts import TimeoutException, StaleElementReferenceException
import time

def delete_existing_meds_func(driver):
    # 删除原有的用药记录
    try:
        # 获取所有用药记录的容器
        child_divs = WebDriverWait(driver, 15).until(
            ec.visibility_of_all_elements_located((By.XPATH, '//*[@id="ext-gen21"]/div'))
        )

        # 检查是否有用药记录
        if not child_divs:
            print("无用药记录")
            return

        # 获取药物名称元素，用于判断列位置
        drug_name = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH,
                                            '/html/body/form/div[2]/div/div[3]/table/tbody/tr/td/div/div/div/div/div/div[1]/div[2]/div/div[1]/table/tbody/tr/td[1]/div'))
        )
        drug_name_value = drug_name.text

        # 从后往前删除（避免索引变化问题）
        for i in range(len(child_divs), 0, -1):
            try:
                # 根据药物名称是否为空确定删除按钮的位置
                if len(drug_name_value) == 0:
                    delete_xpath = f'/html/body/form/div[2]/div/div[3]/table/tbody/tr/td/div/div/div/div/div/div[1]/div[2]/div/div[{i}]/table/tbody/tr/td[6]/div/img'
                else:
                    delete_xpath = f'/html/body/form/div[2]/div/div[3]/table/tbody/tr/td/div/div/div/div/div/div[1]/div[2]/div/div[{i}]/table/tbody/tr/td[5]/div/img'

                # 定位删除按钮
                delete_button = WebDriverWait(driver, 10).until(
                    ec.element_to_be_clickable((By.XPATH, delete_xpath)))

                # 滚动到元素并确保在视图中
                driver.execute_script("""
                    arguments[0].scrollIntoView({
                        behavior: 'auto', 
                        block: 'center',
                        inline: 'center'
                    });
                """, delete_button)

                # 添加短暂等待确保元素稳定
                time.sleep(0.3)

                # 使用JavaScript点击删除按钮（避免遮挡问题）
                # driver.execute_script("arguments[0].click();", delete_button)
                delete_button.click()

                # 处理可能的确认对话框
                try:
                    confirm_btn = WebDriverWait(driver, 3).until(
                        ec.element_to_be_clickable(
                            (By.XPATH, "//button[text()='是']"))
                    )
                    confirm_btn.click()
                except TimeoutException:
                    pass  # 没有确认对话框

                time.sleep(0.5)

                # 等待列表刷新
                WebDriverWait(driver, 3).until(
                    lambda d: len(d.find_elements(By.XPATH, '//*[@id="ext-gen21"]/div')) < len(child_divs)
                )

                # 更新child_divs计数
                child_divs = driver.find_elements(By.XPATH, '//*[@id="ext-gen21"]/div')

            except StaleElementReferenceException:
                print(f"第 {i} 条记录状态已更新，继续操作...")
                # 刷新元素列表
                child_divs = driver.find_elements(By.XPATH, '//*[@id="ext-gen21"]/div')
                continue

            except TimeoutException:
                print(f"第 {i} 条记录删除超时，尝试继续")
                continue

            except Exception as e:
                print(f"删除第 {i} 条记录时出错: {str(e)}")
                driver.save_screenshot(f"delete_error_{i}.png")
                continue
        print("所有用药记录已成功删除")
    except TimeoutException:
        print("没有找到用药记录容器")
    except Exception as e:
        print(f"删除用药记录时发生错误: {str(e)}")
