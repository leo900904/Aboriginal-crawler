#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import requests
from datetime import datetime
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin
import re
from mutagen.mp3 import MP3
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Import specialized modules from crawlers directory
from crawlers.alphabet_crawler import crawl_alphabet_words
from crawlers.sentence_crawler import crawl_sentences
from crawlers.twelve_year_crawler import crawl_twelve_year_course
from crawlers.state import CREATED_FOLDERS
from crawlers.picture_story_crawler import crawl_picture_stories
from crawlers.life_conversation_crawler import crawl_life_conversation
from crawlers.reading_writing_crawler import crawl_reading_writing
from crawlers.culture_crawler import crawl_culture
from crawlers.vocabulary_crawler import crawl_vocabulary
from crawlers.dialogue_crawler import crawl_dialogue
from crawlers.essay_crawler import crawl_essay
# ---------------------------
# Global Settings
# ---------------------------

BASE_DOMAIN = "klokah.tw"

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def download_audio(audio_url, filename, audio_folder):
    """Download audio file and save with specified filename."""
    try:
        full_url = urljoin(f"https://{BASE_DOMAIN}/", audio_url)
        resp = requests.get(full_url, timeout=10)
        if resp.status_code == 200:
            audio_path = os.path.join(audio_folder, filename)
            with open(audio_path, "wb") as f:
                f.write(resp.content)
            logging.info("Successfully downloaded audio: %s" % filename)
        else:
            logging.warning("Failed to download audio, status code: %s, URL: %s", resp.status_code, audio_url)
    except Exception as e:
        logging.error("Error downloading audio: %s, URL: %s", e, audio_url)

def extract_romaji(text):
    """Extract romaji from text."""
    match = re.search(r'\(([^()]+)\)', text)
    if match:
        return f'({match.group(1).strip()})'
    return None

def save_label(word_text, mp3_name, label_file):
    """Save word text and mp3 name to label file."""
    if not word_text:
        return
    try:
        with open(label_file, "a", encoding="utf-8") as f:
            f.write(mp3_name + "\n")
            f.write(word_text + "\n")
            f.write("male\n")
            f.write("one\n")
            f.write("\n")
    except Exception as e:
        logging.error("Error writing to label.txt: %s" % e)

def handle_dropdown(driver, dropdown_id):
    """Handle dropdown menu selection."""
    try:
        dropdown_element = driver.find_element(By.ID, dropdown_id)
        if not dropdown_element.is_displayed():
            return []
        select_obj = Select(dropdown_element)
        return select_obj.options
    except Exception as e:
        logging.error(f"Unable to find or handle dropdown {dropdown_id}: {e}")
        return []

def check_for_content(driver):
    """Check if page has content to crawl."""
    try:
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Ab"))
        )
        return True
    except:
        return False

def select_language(driver, lang_config):
    """選擇語言和方言。"""
    try:
        # 點擊語言切換按鈕
        switch_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".switcher"))
        )
        switch_btn.click()
        time.sleep(1)
    except Exception as e:
        logging.error(f"無法點擊語言切換按鈕：{e}")
        return False, None, None

    try:
        # 點擊主語言
        main_lang_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, f"//a[contains(@class, 'language') and contains(text(), '{lang_config['main_lang']}')]"))
        )
        main_lang_name = main_lang_btn.text.strip()
        main_lang_btn.click()
        time.sleep(1)
    except Exception as e:
        logging.error(f"無法點擊{lang_config['main_lang']}：{e}")
        return False, None, None

    try:
        # 點擊方言
        dialect_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, f"//a[contains(@class, 'dialect') and contains(text(), '{lang_config['dialect']}')]"))
        )
        dialect_name = dialect_btn.text.strip()
        dialect_btn.click()
        time.sleep(2)
    except Exception as e:
        logging.error(f"無法點擊{lang_config['dialect']}：{e}")
        return False, None, None

    return True, main_lang_name, dialect_name

def write_stat_file(main_lang=None, dialect=None, url=None, elapsed_time=None):
    """Write statistics to file."""
    outer_folder = os.path.join(main_lang, dialect)
    stat_path = os.path.join(outer_folder, 'stat.txt')
    
    total_audio_files = 0
    total_duration = 0.0
    
    for folder in CREATED_FOLDERS:
        audio_folder = os.path.join(folder, "audio")
        if os.path.exists(audio_folder):
            audio_files = [f for f in os.listdir(audio_folder) if f.lower().endswith('.mp3')]
            total_audio_files += len(audio_files)
            for fname in audio_files:
                fpath = os.path.join(audio_folder, fname)
                try:
                    audio = MP3(fpath)
                    duration = audio.info.length
                    total_duration += duration
                except Exception as e:
                    logging.warning(f"Unable to read audio duration {fpath}: {e}")
    
    lines = []
    if url:
        lines.append(f"URL: {url}\n")
    if main_lang:
        lines.append(f"Language: {main_lang}\n")
    if dialect:
        lines.append(f"Dialect: {dialect}\n")
    lines.append(f"Total audio files: {total_audio_files}\n")
    lines.append(f"Total duration: {total_duration:.2f} seconds\n")
    
    total_seconds = int(total_duration)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    lines.append(f"Total duration: {hours} hours {minutes} minutes {seconds} seconds\n")
    
    if elapsed_time is not None:
        lines.append(f"Crawling time: {elapsed_time:.2f} seconds\n")
        h = int(elapsed_time) // 3600
        m = (int(elapsed_time) % 3600) // 60
        s = int(elapsed_time) % 60
        lines.append(f"Crawling time: {h} hours {m} minutes {s} seconds\n")
    
    with open(stat_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def setup_driver():
    """設定並返回 Chrome WebDriver。"""
    chrome_options = Options()
    # chrome_options.add_argument('--headless')  # 移除無頭模式!!! 不開正在爬的畫面可以爬得更快  移除無頭模式!!! 不開正在爬的畫面可以爬得更快  
    # 有時候 Selenium 會抓不到裡面的內容（尤其是 headless 模式或某些驅動）。
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # 優先使用手動指定的 ChromeDriver 路徑
    manual_paths = [
        r"C:\chromedriver-win64\chromedriver.exe",  # 您的 ChromeDriver 位置
        r"C:\chromedriver\chromedriver.exe",  # 備用位置
        r".\chromedriver.exe",  # 當前目錄
    ]
    
    service = None
    # 先嘗試手動路徑
    for path in manual_paths:
        try:
            if os.path.exists(path):
                service = Service(path)
                logging.info(f"使用手動指定的 ChromeDriver 路徑: {path}")
                break
        except Exception as e:
            logging.warning(f"嘗試路徑 {path} 失敗: {e}")
            continue
    
    # 如果手動路徑都失敗，嘗試 WebDriverManager
    if service is None:
        try:
            logging.info("手動路徑不可用，嘗試使用 WebDriverManager...")
            service = Service(ChromeDriverManager().install())
            logging.info("WebDriverManager 成功")
        except Exception as e:
            logging.error(f"WebDriverManager 也失敗: {e}")
            # 最後嘗試系統 PATH
            try:
                service = Service("chromedriver")
                logging.info("使用系統 PATH 中的 chromedriver")
            except:
                logging.error("所有 ChromeDriver 來源都失敗")
                raise Exception("無法找到可用的 ChromeDriver")
    
    # 嘗試啟動瀏覽器，如果版本不匹配，回退到 WebDriverManager
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.maximize_window()
        return driver
    except Exception as e:
        if "version" in str(e).lower() or "supports" in str(e).lower():
            logging.warning(f"版本不匹配，嘗試使用 WebDriverManager 自動下載匹配版本: {e}")
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.maximize_window()
                return driver
            except Exception as e2:
                logging.error(f"WebDriverManager 備用方案也失敗: {e2}")
                raise e2
        else:
            raise e


def main():
    """主程式。"""
    # 初始化 WebDriver
    driver = setup_driver()
    
    # 語言設定
    LANG_CONFIG = {
        "main_lang": "排灣語",
        "dialect": "東排灣語"
    }
    
    # LANG_CONFIG = {
    #     "main_lang": "阿美語",
    #     "dialect": "海岸阿美語"
    # }
    
    try:
        # 只建立語言和方言資料夾
        lang_folder = LANG_CONFIG["main_lang"]
        dialect_folder = os.path.join(lang_folder, LANG_CONFIG["dialect"])
        os.makedirs(dialect_folder, exist_ok=True)

        crawlers = {
            # '字母篇': {
            #     'url': 'https://web.klokah.tw/extension/ab_practice/index.php',
            #     'func': crawl_alphabet_words,
            #     'folder': '字母篇'
            # }
            # ,
            # '句型篇國中版': {
            #     'url': 'https://web.klokah.tw/extension/sp_junior/practice.php',
            #     'func': crawl_sentences,
            #     'folder': '句型篇國中版'
            # }
            # ,
            # '句型篇高中版': {
            #     'url': 'https://web.klokah.tw/extension/sp_senior/practice.php',
            #     'func': crawl_sentences,
            #     'folder': '句型篇高中版'
            # }
            # ,
            # '十二年國教課程': {
            #     'url': 'https://web.klokah.tw/twelve/learn.php',
            #     'func': crawl_twelve_year_course,
            #     'folder': '十二年國教課程'
            # }
            # ,
            # '圖畫故事篇': {
            #     'url': 'https://web.klokah.tw/extension/ps_practice/',
            #     'func': crawl_picture_stories,
            #     'folder': '圖畫故事篇'
            # }
            # ,
            # '生活會話篇': {
            #     'url': 'https://web.klokah.tw/extension/con_practice/',
            #     'func': crawl_life_conversation,
            #     'folder': '生活會話篇'
            # }
            # ,
            # '閱讀書寫篇': {
            #     'url': 'https://web.klokah.tw/extension/rd_practice/',
            #     'func': crawl_reading_writing,
            #     'folder': '閱讀書寫篇'
            # }
            # ,
            # '文化篇': {
            #     'url': 'https://web.klokah.tw/extension/cu_practice/',
            #     'func': crawl_culture,
            #     'folder': '文化篇'
            # }
            # ,
            # '學習詞表': {
            #     'url': 'https://web.klokah.tw/vocabulary/', # 到第32個小輪就會斷掉 爬不到 所有要再改 start_number=1 變成32開始繼續爬
            #     'func': crawl_vocabulary,
            #     'folder': '學習詞表'
            # },
            # '情境族語': {
            #     'url': 'https://web.klokah.tw/dialogue/', 
            #     'func': crawl_dialogue,
            #     'folder': '情境族語'  # 學習三 的 單詞學習 爬不出來 明明學習二的單詞學習就爬的到 
            # },
            # '族語短文': {
            #     'url': 'https://web.klokah.tw/essay/',
            #     'func': crawl_essay,
            #     'folder': '族語短文'
            # },  

            # 還有 10 個 不然就是超長的那種 30幾分鐘 的影片
            # 補充教材： 閱讀文本 
            # 教材教具學習： WAWA點點樂 、 主題式掛圖的身體 親屬 山川自然 動物 、 LIMA有聲書 
            # 開放平台： 繪本平台 、 動畫平台 、 影音中心 、 自編教材 、 教案平台 、 句法演練平台 、 族語學習 podcast 甚至可以用之前訓練的模型辨識之後 再加入到訓練裡面 
            # 族語影片： 看影片學族語 、 或是再用訓練出來的模型 來去做 弱標註(自動標註)
            # 族語翻譯精靈sisil  隨時翻譯 線上即時翻譯軟體 只能翻譯文字 放輕鬆
        }
        for name, config in crawlers.items():
            try:
                logging.info(f"開始爬取 {name}")
                driver.get(config['url'])
                time.sleep(2)
                ok, main_lang, dialect = select_language(driver, LANG_CONFIG)
                if not ok:
                    logging.error("選擇語言失敗，程式終止")
                    return
                # 不要再呼叫 create_base_folders
                config['func'](driver, main_lang, dialect, config['folder'])
                logging.info(f"完成爬取 {name}")
            except Exception as e:
                logging.error(f"爬取 {name} 時出錯：{e}")
                continue
                
    finally:
        # 關閉 WebDriver
        driver.quit()

if __name__ == '__main__':
    main() 