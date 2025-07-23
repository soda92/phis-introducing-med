import difflib

def is_drug_name_similar(drug_name, drug_names_set, threshold=0.8):
    """
    判断一个药物名称是否与集合中的任何药物名称相似。

    :param drug_name: 当前待检查的药物名称
    :param drug_names_set: 已知药物名称的集合
    :param threshold: 相似度阈值，默认0.8
    :return: 如果相似的药物存在，则返回True，否则返回False
    """
    for name in drug_names_set:
        # 计算相似度
        similarity = difflib.SequenceMatcher(None, drug_name, name).ratio()

        # 如果相似度达到阈值，返回True
        if similarity >= threshold:
            return True

    # 如果没有找到相似药物，返回False
    return False