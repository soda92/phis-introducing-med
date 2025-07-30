from kapybara import By

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
