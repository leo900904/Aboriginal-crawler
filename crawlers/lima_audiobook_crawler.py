import os
import logging
import requests
from .utils import download_audio, save_label

# 使用時 utils.py 更改BASE_DOMAIN = "web.klokah.tw"
# main.py 中在 crawlers = {     補上
# 'LIMA有聲書': {
#                 'url': 'https://web.klokah.tw/lima/',
#                 'func': crawl_lima,
#                 'folder': 'LIMA有聲書'
#             },    

BASE_URL = "https://web.klokah.tw/lima"

# 教材類型對應 JSON 區塊與資料夾名稱
CONTENT_TYPES = {
    "vocabulary": "字彙",
    "conversation": "會話",
    "question": "問答",
    "story": "故事"
}

def get_next_counter(audio_folder):
    """獲取下一個可用的檔案編號"""
    try:
        files = [f for f in os.listdir(audio_folder) if f.lower().endswith('.mp3')]
        if not files:
            return 1
        nums = [int(os.path.splitext(f)[0]) for f in files if os.path.splitext(f)[0].isdigit()]
        return max(nums) + 1 if nums else 1
    except Exception:
        return 1

def setup_folder_structure(main_lang, dialect, folder_name):
    """創建標準資料夾結構"""
    try:
        # 創建主題資料夾
        topic_folder = os.path.join(main_lang, dialect, folder_name)
        os.makedirs(topic_folder, exist_ok=True)
        
        # 創建 -10 子資料夾
        record_folder = os.path.join(topic_folder, f"{folder_name}-10")
        os.makedirs(record_folder, exist_ok=True)
        
        # 創建音檔資料夾
        audio_folder = os.path.join(record_folder, "audio")
        os.makedirs(audio_folder, exist_ok=True)
        
        # 創建並初始化 label.txt
        label_file = os.path.join(record_folder, "label.txt")
        if not os.path.exists(label_file):
            with open(label_file, "w", encoding="utf-8") as f:
                f.write("")
                
        logging.info(f"創建資料夾結構: {record_folder}")
        return record_folder, audio_folder, label_file
    except Exception as e:
        logging.error(f"創建資料夾結構失敗: {e}")
        return None, None, None

def crawl_lima(driver, main_lang, dialect, folder_name):
    """
    爬取 LIMA 有聲書資料。
    資料將儲存在標準的 main_lang/dialect/folder_name/folder_name-10/audio/ 結構下。
    """
    lang_id = 6  # 預設賽考利克泰雅語，可日後改為自動查詢
    max_lessons = 10  # 可根據實際課程數做調整

    # 建立標準資料夾結構
    record_folder, audio_folder, label_file = setup_folder_structure(main_lang, dialect, folder_name)
    if not record_folder:
        logging.error("無法創建資料夾結構")
        return

    # 獲取起始檔案編號
    file_counter = get_next_counter(audio_folder)

    for lesson_no in range(1, max_lessons + 1):
        json_url = f"{BASE_URL}/json/{lang_id}/{lesson_no}.json"
        try:
            resp = requests.get(json_url)
            if resp.status_code != 200:
                logging.warning(f"無法取得 JSON：{json_url}")
                continue
            data = resp.json()
        except Exception as e:
            logging.error(f"下載或解析 JSON 錯誤：{json_url}, {e}")
            continue

        for content_key, subfolder in CONTENT_TYPES.items():
            if content_key not in data:
                continue

            entries = data[content_key]
            if not isinstance(entries, list):
                continue

            logging.info(f"處理 {subfolder} - 第 {lesson_no} 課")

            for i, item in enumerate(entries):
                if not item or "audio" not in item or not item.get("ab"):
                    continue

                # 使用動態檔案編號
                filename = f"{file_counter:04d}.mp3"

                # story 固定接 -18.mp3
                if content_key == "story":
                    audio_file = f"{item['audio']}-18.mp3"
                else:
                    audio_file = f"{item['audio']}.mp3"

                # 組合完整的下載路徑
                audio_url = f"lima/sound/{lang_id}/{content_key}/{audio_file}"
                
                # 下載音檔
                download_audio(audio_url, filename, audio_folder)

                # 使用標準的 save_label 函數儲存標籤
                text = item['ch'] + '(' + item['ab'] + ')'
                save_label(text, filename, label_file)

                logging.info(f"已爬取 {filename}: {text}")
                file_counter += 1

            logging.info(f"完成 {subfolder} - 第 {lesson_no} 課")

    logging.info(f"LIMA有聲書爬取完成，共處理 {file_counter - get_next_counter(audio_folder)} 個檔案")

