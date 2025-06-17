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

def crawl_lima(driver, main_lang, dialect, folder_name):
    """
    爬取 LIMA 有聲書資料。
    資料將儲存在 main_lang/dialect/folder_name/... 結構下。
    """
    lang_id = 6  # 預設賽考利克泰雅語，可日後改為自動查詢
    max_lessons = 10  # 可根據實際課程數做調整

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

            # 修改：加上 main_lang / dialect / folder_name
            audio_folder = os.path.join(main_lang, dialect, folder_name, subfolder, f"lesson_{lesson_no}")
            os.makedirs(audio_folder, exist_ok=True)
            label_path = os.path.join(audio_folder, "label.txt")

            # 清空 label.txt（避免累積）
            open(label_path, "w", encoding="utf-8").close()

            for i, item in enumerate(entries):
                if not item or "audio" not in item or not item.get("ab"):
                    continue

                filename = f"{i+1:04d}.mp3"

                # story 固定接 -18.mp3
                if content_key == "story":
                    audio_file = f"{item['audio']}-18.mp3"
                else:
                    audio_file = f"{item['audio']}.mp3"

                # 組合完整的下載路徑
                audio_url = f"lima/sound/{lang_id}/{content_key}/{audio_file}"
                download_audio(audio_url, filename, audio_folder)

                # 儲存對應 label
                text = item['ch'] + '(' + item['ab'] + ')'
                save_label(text, filename, label_path)

            logging.info(f"完成 {content_key} - 第 {lesson_no} 課")

