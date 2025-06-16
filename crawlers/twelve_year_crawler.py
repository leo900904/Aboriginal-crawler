#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import re
import requests
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from .state import CREATED_FOLDERS
from .utils import download_audio, save_label, extract_romaji
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

def wait_for_network_idle(driver, idle_time=1.0, check_interval=0.2, timeout=15):
    """
    等待 network 沒有新請求 idle_time 秒，最多 timeout 秒。
    """
    start = time.time()
    last_count = len(driver.requests)
    last_change = time.time()
    while True:
        now_count = len(driver.requests)
        if now_count != last_count:
            last_change = time.time()
            last_count = now_count
        if time.time() - last_change >= idle_time:
            break
        if time.time() - start > timeout:
            print("Network idle 等待超時")
            break
        time.sleep(check_interval)

def clean_label_line(label_line):
    # 把所有換行符號都換成空白
    return label_line.replace('\n', '').replace('\r', '').strip()

def clean_romaji(romaji):
    return re.sub(r'\([^\)]*\)', '', romaji).strip()

def crawl_twelve_year_course(driver, main_lang, dialect, folder_name):
    """爬取十二年國教課程內容。"""
    # 先建立主題資料夾
    topic_folder = os.path.join(main_lang, dialect, folder_name)
    os.makedirs(topic_folder, exist_ok=True)
    # 再建立主題-10子資料夾
    record_folder = os.path.join(topic_folder, f"{folder_name}-10")
    os.makedirs(record_folder, exist_ok=True)
    audio_folder = os.path.join(record_folder, "audio")
    label_txt = os.path.join(record_folder, "label.txt")
    audio_map_txt = os.path.join(record_folder, "audio_map.txt")
    error_txt = os.path.join(record_folder, "error.txt")
    os.makedirs(audio_folder, exist_ok=True)
    if not os.path.exists(label_txt):
        with open(label_txt, "w", encoding="utf-8") as f:
            f.write("")
    if not os.path.exists(audio_map_txt):
        with open(audio_map_txt, "w", encoding="utf-8") as f:
            f.write("")
    if not os.path.exists(error_txt):
        with open(error_txt, "w", encoding="utf-8") as f:
            f.write("")

    # 全域流水號計數器
    def get_next_counter():
        files = [f for f in os.listdir(audio_folder) if f.lower().endswith('.mp3')]
        if not files:
            return 1
        nums = [int(os.path.splitext(f)[0]) for f in files if os.path.splitext(f)[0].isdigit()]
        return max(nums) + 1 if nums else 1
    counter = get_next_counter()

    start_url = "https://web.klokah.tw/twelve/learn.php"
    driver.get(start_url)
    time.sleep(1)
    level_btns = driver.find_elements(By.CSS_SELECTOR, '#nine-learn-level .nine-level-btn')
    for level_btn in level_btns:
        level_text = level_btn.text.strip()
        print(f"進入階級: {level_text}")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", level_btn)
        level_btn.click()
        time.sleep(1)
        lesson_btns = driver.find_elements(By.CSS_SELECTOR, 'div#nine-learn-class > a.nine-class-btn')
        for lesson_btn in lesson_btns:
            lesson_text = lesson_btn.text.strip()
            print(f"  進入課程: {lesson_text}")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lesson_btn)
            driver.requests.clear()  # 先清空
            lesson_btn.click()       # 再點擊
            wait_for_network_idle(driver, idle_time=1.0, check_interval=0.2, timeout=15)
            # 這時候所有 mp3 請求都已經送出
            # 取得課程編號（如01、02...）
            lesson_code = re.search(r'第(\d+)課', lesson_text)
            if lesson_code:
                lesson_prefix = lesson_code.group(1).zfill(2)
            else:
                lesson_prefix = ''
            # 取得所有 mp3 請求
            mp3_requests = [
                r for r in driver.requests
                if r.response and '/twelve/sound/' in r.url and r.url.split('?')[0].endswith('.mp3')
            ]
            b_btns = driver.find_elements(By.CSS_SELECTOR, 'a.play-btn[id^="play-btn-"]')
            if len(mp3_requests) < len(b_btns) + 1:  # +1 for A 段
                print(f"mp3 載入數量不足({len(mp3_requests)}/{len(b_btns)+1})，再等 2 秒重抓")
                time.sleep(2)
                mp3_requests = [
                    r for r in driver.requests
                    if r.response and '/twelve/sound/' in r.url and r.url.split('?')[0].endswith('.mp3')
                ]
            # 過濾只要 XX-A.mp3 和 XX-B-1.mp3, XX-B-2.mp3 ...
            filtered_mp3 = {}
            for req in mp3_requests:
                filename = os.path.basename(req.url.split('?')[0])
                if re.match(rf'^{lesson_prefix}-A\.mp3$', filename) or re.match(rf'^{lesson_prefix}-B-\d+\.mp3$', filename):
                    filtered_mp3[filename] = req.url
            # 取得主課文羅馬拼音和中文
            try:
                a_div = driver.find_element(By.ID, "nine-learn-title")
                # 取出下層第一個 div 的 text
                inner_div = a_div.find_element(By.TAG_NAME, "div")
                main_romaji = inner_div.text.split('\n')[0].replace('"', '').strip()
                # 中文
                main_chinese = inner_div.find_element(By.TAG_NAME, "span").text.strip()
            except Exception:
                main_romaji = ''
                main_chinese = ''
            # 取得所有 B 段的 play-btn
            lesson_items = driver.find_elements(By.CSS_SELECTOR, 'div.lesson-item')
            downloaded = set()  # 確保每一課都初始化
            for filename, url in filtered_mp3.items():
                if filename in downloaded:
                    continue
                for attempt in range(3):
                    label_line = ""
                    if re.match(rf'^{lesson_prefix}-A\.mp3$', filename):
                        label_line = f"{main_chinese}({clean_romaji(main_romaji)})" if main_chinese and main_romaji else main_chinese or (f"({clean_romaji(main_romaji)})" if main_romaji else "")
                    elif re.match(rf'^{lesson_prefix}-B-(\d+)\.mp3$', filename):
                        b_idx = int(re.match(rf'^{lesson_prefix}-B-(\d+)\.mp3$', filename).group(1)) - 1
                        try:
                            lesson_item = lesson_items[b_idx]
                            lesson_text_div = lesson_item.find_element(By.CSS_SELECTOR, 'div.lesson-text')
                            text_blocks = lesson_text_div.find_elements(By.XPATH, './div[starts-with(@id, "text-")]')
                            words = []
                            for block in text_blocks:
                                words += [w.get_attribute("textContent") for w in block.find_elements(By.CSS_SELECTOR, 'div.textWord')]
                            romaji = " ".join(words).strip()
                            chs_div = lesson_item.find_element(By.CSS_SELECTOR, f'div[id^="chs-"]')
                            chinese = chs_div.get_attribute("textContent").strip()
                        except Exception:
                            romaji = ""
                            chinese = ""
                        label_line = f"{chinese}({clean_romaji(romaji)})" if chinese and romaji else chinese or (f"({clean_romaji(romaji)})" if romaji else "")
                    if label_line.strip():
                        audio_path = os.path.join(audio_folder, f"{str(counter).zfill(4)}.mp3")
                        try:
                            resp = requests.get(url)
                            with open(audio_path, "wb") as f:
                                f.write(resp.content)
                            print("下載:", f"{str(counter).zfill(4)}.mp3")
                            downloaded.add(filename)
                            with open(label_txt, "a", encoding="utf-8") as f:
                                f.write(f"{str(counter).zfill(4)}.mp3\n")
                                f.write(clean_label_line(label_line) + "\n")
                                f.write("male\n")
                                f.write("one\n")
                                f.write("\n")
                            with open(audio_map_txt, "a", encoding="utf-8") as f:
                                f.write(f"{str(counter).zfill(4)}.mp3\t階級:{level_text}\t課程:{lesson_text}\t原始檔名:{filename}\n")
                            counter += 1
                        except Exception as e:
                            print(f"下載失敗: {filename}, {e}")
                        break
                    else:
                        print(f"{filename} 文字標籤抓不到，重試第{attempt+1}次")
                        time.sleep(1)
                else:
                    print(f"{filename} 文字標籤最終還是抓不到，跳過")
                    with open(error_txt, "a", encoding="utf-8") as f:
                        f.write(f"{str(counter).zfill(4)}.mp3\t階級:{level_text}\t課程:{lesson_text}\t原始檔名:{filename}\n")
    print("所有音檔下載完成！")

