#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import requests
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from seleniumwire import webdriver  # 用於攔截 network 請求
import re

def download_mp3_from_network(driver, audio_folder, mp3_name):
    """從 network 請求中下載最新的 mp3 檔案"""
    for request in reversed(driver.requests):  # 反向找最新的
        if request.response and request.url.endswith('.mp3'):
            try:
                resp = requests.get(request.url)
                if resp.status_code == 200 and resp.headers.get('Content-Type', '').startswith('audio'):
                    audio_path = os.path.join(audio_folder, mp3_name)
                    with open(audio_path, "wb") as f:
                        f.write(resp.content)
                    print(f"已下載: {audio_path}")
                else:
                    print(f"下載失敗: {request.url} 狀態碼: {resp.status_code} Content-Type: {resp.headers.get('Content-Type')}")
            except Exception as e:
                print(f"下載音檔失敗: {request.url}", e)
            break  # 只抓一個

def clean_romaji(romaji):
    return re.sub(r'\([^\)]*\)', '', romaji).strip()

def crawl_reading_text(driver, main_lang, dialect, folder_name):
    """爬取閲讀文本內容（含多分頁），資料夾結構與字母篇一致。"""
    # 建立主題資料夾與 -10 子資料夾
    topic_folder = os.path.join(main_lang, dialect, folder_name)
    os.makedirs(topic_folder, exist_ok=True)
    record_folder = os.path.join(topic_folder, f"{folder_name}-10")
    os.makedirs(record_folder, exist_ok=True)
    audio_folder = os.path.join(record_folder, "audio")
    os.makedirs(audio_folder, exist_ok=True)
    label_txt = os.path.join(record_folder, "label.txt")
    if not os.path.exists(label_txt):
        with open(label_txt, "w", encoding="utf-8") as f:
            f.write("")

    # 全域流水號計數器
    def get_next_counter():
        files = [f for f in os.listdir(audio_folder) if f.lower().endswith('.mp3')]
        if not files:
            return 1
        nums = [int(os.path.splitext(f)[0]) for f in files if os.path.splitext(f)[0].isdigit()]
        return max(nums) + 1 if nums else 1
    counter = get_next_counter()

    # 進入主頁
    start_url = "https://web.klokah.tw/extension/readingtext/"
    driver.get(start_url)
    time.sleep(1)
    # 找到所有故事連結
    story_links = driver.find_elements(By.CSS_SELECTOR, 'a.link.text')
    print(f"共找到 {len(story_links)} 個故事")
    for story_idx, link in enumerate(story_links):
        href = link.get_attribute('href')
        if not href:
            continue
        driver.get(href)
        time.sleep(1)
        print(f"進入故事 {story_idx+1}")
        while True:
            # 切換到 iframe
            try:
                iframe = driver.find_element(By.ID, "text-frame")
                driver.switch_to.frame(iframe)
                time.sleep(0.5)
            except Exception:
                print("找不到iframe，跳過本頁")
                break
            # 找到所有句子區塊
            blocks = driver.find_elements(By.CSS_SELECTOR, "div#read-main > div")
            for block in blocks:
                try:
                    play_btn = block.find_element(By.CSS_SELECTOR, "button.read-play-btn")
                    mp3_name = f"{str(counter).zfill(4)}.mp3"
                    # 羅馬拼音
                    words = [w.text for w in block.find_elements(By.CSS_SELECTOR, "div.read-sentence.Ab div.word")]
                    romaji = " ".join(words).strip()
                    # 中文（用 XPath，抓到即使 hidden 的元素，並用 textContent 取值）
                    try:
                        ch_div = block.find_element(By.XPATH, ".//div[contains(@class, 'read-sentence') and contains(@class, 'Ch')]")
                        chinese = ch_div.get_attribute('textContent').strip()
                    except Exception as e:
                        print(f"[錯誤] 抓不到中文，錯誤：{e}")
                        chinese = ""
                    # 先清空 network 請求
                    driver.requests.clear()
                    # 點擊播放按鈕
                    play_btn.click()
                    time.sleep(1.5)
                    # 從 network 下載 mp3
                    download_mp3_from_network(driver, audio_folder, mp3_name)
                    # 寫入 label.txt
                    with open(label_txt, "a", encoding="utf-8") as f:
                        if chinese:
                            f.write(f"{mp3_name}\n")
                            f.write(f"{chinese}({clean_romaji(romaji)})\n")
                        else:
                            f.write(f"{mp3_name}\n")
                            f.write(f"({clean_romaji(romaji)})\n")
                        f.write("female\n")
                        f.write("one\n")
                        f.write("\n")
                    print(f"已爬取: {mp3_name} {chinese}({clean_romaji(romaji)})")
                    counter += 1
                except Exception as e:
                    print("句子區塊解析失敗：", e)
            # 切回主頁
            driver.switch_to.default_content()
            # 檢查是否有下一頁按鈕
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a.next_1")
                next_btn.click()
                time.sleep(1)
            except NoSuchElementException:
                print("本故事已無下一頁，結束本故事")
                break
            except Exception as e:
                print("下一頁按鈕異常：", e)
                break
    print("閲讀文本爬取完成！") 