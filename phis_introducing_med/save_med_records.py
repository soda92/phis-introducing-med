from pathlib import Path
import csv

# 新增：CSV文件路径
OUTPUT_FILE = Path('./执行结果/用药记录.csv')


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
