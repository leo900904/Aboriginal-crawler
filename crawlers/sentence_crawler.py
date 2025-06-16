#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import requests
from datetime import datetime
from selenium import webdriver
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
from .state import CREATED_FOLDERS
from .utils import download_audio, save_label, extract_romaji

# 全域變數
COUNTER = 1
current_path = []

def handle_dropdown(driver, dropdown_id):
    """處理下拉選單。"""
    try:
        dropdown_element = driver.find_element(By.ID, dropdown_id)
        if not dropdown_element.is_displayed():
            return []
        select_obj = Select(dropdown_element)
        return select_obj.options
    except Exception as e:
        logging.error(f"無法找到或處理下拉選單 {dropdown_id}: {e}")
        return []

def check_for_content(driver):
    """檢查頁面上是否有需要抓取的內容。"""
    try:
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Ab"))
        )
        return True
    except:
        return False

def get_word_and_audio_info(driver, audio_folder, label_file):
    """獲取單字和音檔資訊。"""
    global COUNTER
    # 先抓所有顯示中的 part（如 partA、partB...）
    part_divs = [div for div in driver.find_elements(By.CSS_SELECTOR, "div[class^='part']") if div.is_displayed()]
    found_any = False
    if part_divs:
        for part in part_divs:
            # 進到每個 part 裡的 text 區塊
            text_divs = part.find_elements(By.CSS_SELECTOR, "div.text")
            for text_div in text_divs:
                # 1. 找羅馬拼音 Ab
                ab_divs = text_div.find_elements(By.CSS_SELECTOR, "div[class*='Ab']")
                romaji_lines = []
                for div in ab_divs:
                    text = div.text.strip()
                    if not text:
                        continue
                    if re.match(r'^\(.*\)$', text):
                        continue
                    text = re.sub(r'^[A-Z]\s*[:：]\s*', '', text)
                    if not text:
                        continue
                    if re.search(r'[\u4e00-\u9fff]', text):
                        continue
                    romaji_lines.append(text)
                if not romaji_lines:
                    continue
                romaji_text = ' '.join(romaji_lines)
                # 2. 找中文 Ch
                ch_divs = text_div.find_elements(By.CSS_SELECTOR, "div[class*='Ch']")
                ch_lines = []
                for div in ch_divs:
                    text = div.text.strip()
                    if not text:
                        continue
                    if re.match(r'^\(.*\)$', text):
                        continue
                    text = re.sub(r'^[A-Z]\s*[:：]\s*', '', text)
                    if not text:
                        continue
                    if not re.search(r'[\u4e00-\u9fff]', text):
                        continue
                    text = re.sub(r'\([^)]*\)', '', text)
                    ch_lines.append(text)
                ch_text = ''.join(ch_lines)
                label_line = f"{ch_text}({romaji_text})"
                # 3. 找 mp3 連結
                try:
                    audio_tag = part.find_element(By.CSS_SELECTOR, "a[class*='audio_1']")
                    audio_url = audio_tag.get_attribute("url")
                except Exception as e:
                    continue
                if not audio_url:
                    continue
                mp3_name = str(COUNTER).zfill(4) + ".mp3"
                save_label(label_line, mp3_name, label_file)
                download_audio(audio_url, mp3_name, audio_folder)
                COUNTER += 1
                found_any = True
        return found_any
    # 如果沒有 part 結構，走原本的方式
    ab_divs = driver.find_elements(By.CSS_SELECTOR, "div.Ab")
    romaji_lines = []
    for div in ab_divs:
        text = div.text.strip()
        if not text:
            continue
        if re.match(r'^\(.*\)$', text):
            continue
        text = re.sub(r'^[A-Z]\s*[:：]\s*', '', text)
        if not text:
            continue
        if re.search(r'[\u4e00-\u9fff]', text):
            continue
        romaji_lines.append(text)
    ab_text = ' '.join(romaji_lines)
    ch_divs = driver.find_elements(By.CSS_SELECTOR, "div.Ch")
    ch_lines = []
    for div in ch_divs:
        text = div.text.strip()
        if not text:
            continue
        if re.match(r'^\(.*\)$', text):
            continue
        text = re.sub(r'^[A-Z]\s*[:：]\s*', '', text)
        if not text:
            continue
        if not re.search(r'[\u4e00-\u9fff]', text):
            continue
        text = re.sub(r'\([^)]*\)', '', text)
        ch_lines.append(text)
    ch_text = ''.join(ch_lines)
    try:
        audio_tag = driver.find_element(By.CSS_SELECTOR, "a.audio_Ab")
        audio_url = audio_tag.get_attribute("url")
    except:
        audio_url = None
    if not ab_text or not audio_url:
        return False
    label_line = f"{ch_text}({clean_romaji(ab_text)})"
    mp3_name = str(COUNTER).zfill(4) + ".mp3"
    save_label(label_line, mp3_name, label_file)
    download_audio(audio_url, mp3_name, audio_folder)
    COUNTER += 1
    return True

def traverse_dropdowns_recursive(driver, dropdown_ids, level=0, main_lang=None, dialect=None, base_folder=None):
    """遞迴遍歷下拉選單。"""
    global current_path, COUNTER
    
    # 如果已經超過下拉選單的層級，直接檢查內容
    if level >= len(dropdown_ids):
        if check_for_content(driver):
            # 以 base_folder 為基底建立子資料夾
            topic_folder = f"{current_path[0]}-10"
            record_folder = os.path.join(main_lang, dialect, base_folder, topic_folder) if base_folder else os.path.join(main_lang, dialect, topic_folder)
            os.makedirs(record_folder, exist_ok=True)
            audio_folder = os.path.join(record_folder, "audio")
            label_file = os.path.join(record_folder, "label.txt")
            os.makedirs(audio_folder, exist_ok=True)
            if not os.path.exists(label_file):
                with open(label_file, "w", encoding="utf-8") as f:
                    f.write("")
            get_word_and_audio_info(driver, audio_folder, label_file)
        return
        
    options = handle_dropdown(driver, dropdown_ids[level])
    if not options:
        traverse_dropdowns_recursive(driver, dropdown_ids, level + 1, main_lang, dialect, base_folder)
        return
    for opt in options:
        text = opt.text.strip()
        if not text or "請選擇" in text or opt.get_attribute("value") == "0":
            continue
        try:
            Select(driver.find_element(By.ID, dropdown_ids[level])).select_by_visible_text(text)
            time.sleep(1)
            if len(current_path) > level:
                current_path = current_path[:level]
            elif len(current_path) < level:
                current_path += [''] * (level - len(current_path))
            current_path.append(text)
            try:
                logging.info(f"正在探索：{' > '.join(current_path)}")
                traverse_dropdowns_recursive(driver, dropdown_ids, level + 1, main_lang, dialect, base_folder)
            finally:
                current_path.pop()
        except Exception as e:
            logging.error(f"{' > '.join(current_path)}：處理選項 '{text}' 時發生錯誤: {e}")
            continue

def crawl_sentences(driver, main_lang, dialect, folder_name):
    """爬取句型內容。"""
    global current_path
    current_path = []
    # 先建立主題資料夾
    base_folder = os.path.join(main_lang, dialect, folder_name)
    os.makedirs(base_folder, exist_ok=True)
    dropdown_ids = ['sel_type', 'sel_class', 'sel_item']
    traverse_dropdowns_recursive(driver, dropdown_ids, 0, main_lang, dialect, folder_name)

def process_content(driver, selected_options, main_lang, dialect):
    """處理頁面內容。"""
    # 建立資料夾路徑
    folder_path = os.path.join(main_lang, dialect, *selected_options)
    audio_folder = os.path.join(folder_path, "audio")
    os.makedirs(audio_folder, exist_ok=True)
    CREATED_FOLDERS.add(folder_path)
    
    # 初始化 label.txt
    label_path = os.path.join(folder_path, "label.txt")
    if not os.path.exists(label_path):
        with open(label_path, "w", encoding="utf-8") as f:
            f.write("")
    
    # 計算現有檔案數量
    counter = len([f for f in os.listdir(audio_folder) if f.lower().endswith('.mp3')]) + 1
    
    # 獲取單字和音檔資訊
    get_word_and_audio_info(driver, counter, audio_folder, label_path)

def log_empty_branch(selected_options):
    """記錄空分支。"""
    with open("empty_branches.txt", "a", encoding="utf-8") as f:
        f.write(" -> ".join(selected_options) + "\n")

def clean_romaji(romaji):
    return re.sub(r'\([^\)]*\)', '', romaji).strip() 