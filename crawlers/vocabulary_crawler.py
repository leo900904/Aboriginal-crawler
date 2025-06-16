#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from crawlers.utils import download_audio, save_label, clean_romaji
import subprocess
import tempfile
import requests

def convert_wav_to_mp3(wav_data, output_mp3_path):
    """將 WAV 數據轉換為 MP3 文件"""
    try:
        # 創建臨時 WAV 文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav.write(wav_data)
            temp_wav_path = temp_wav.name

        # 使用 ffmpeg 轉換為 MP3
        subprocess.run([
            'ffmpeg', '-i', temp_wav_path,
            '-acodec', 'libmp3lame', '-y',
            output_mp3_path
        ], check=True, capture_output=True)

        # 刪除臨時文件
        os.unlink(temp_wav_path)
        return True
    except Exception as e:
        logging.error(f"轉換音檔格式失敗: {e}")
        return False

def wait_for_vocabulary_content(driver, timeout=10):
    """等待詞表頁面的內容完全加載"""
    try:
        # 等待阿美語文字出現
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#vo-show-ab"))
        )
        # 等待中文翻譯出現
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#vo-show-ch"))
        )
        # 等待播放按鈕出現
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button#vo-btn-ab"))
        )
        return True
    except Exception as e:
        logging.warning(f"等待詞表內容超時: {e}")
        return False

def get_folder_name(driver):
    """獲取當前大輪的資料夾名稱"""
    try:
        cate_div = driver.find_element(By.CSS_SELECTOR, "div.vo-cate[data-value]")
        folder_name = cate_div.get_attribute("data-value")
        return folder_name
    except Exception as e:
        logging.error(f"無法獲取資料夾名稱: {e}")
        return None

def clean_text(text):
    """清理文字，移除括號及其內容"""
    # 使用正則表達式移除括號及其內容
    cleaned = re.sub(r'\([^)]*\)', '', text)
    return cleaned.strip()

def wait_for_wav_file(driver, current_folder, page_counter, max_retries=5, wait_time=3):
    """等待並檢查 WAV 檔案是否出現在 network 中"""
    expected_wav = f"{current_folder[:2]}_{page_counter:02d}.wav"
    
    for retry in range(max_retries):
        # 清除之前的請求記錄
        driver.requests.clear()
        
        # 點擊播放按鈕觸發音檔載入
        try:
            play_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button#vo-btn-ab"))
            )
            play_btn.click()
            time.sleep(wait_time)  # 增加等待時間
        except Exception as e:
            logging.warning(f"點擊播放按鈕失敗: {e}")
            time.sleep(1)  # 失敗後稍等一下
            continue
            
        # 檢查 network 中的 WAV 文件
        for request in driver.requests:
            if request.response and request.url.endswith(expected_wav):
                return request.url
                
        logging.info(f"第 {retry + 1} 次嘗試未找到音檔 {expected_wav}，等待後重試")
        time.sleep(1)  # 每次重試之間增加額外等待
    
    return None

def process_vocabulary_page(driver, audio_folder, label_file, jump_file, current_folder, page_counter, file_counter):
    """處理單個詞表頁面"""
    try:
        if not wait_for_vocabulary_content(driver):
            return False, file_counter

        # 等待並檢查 WAV 檔案
        wav_url = wait_for_wav_file(driver, current_folder, page_counter)

        # 如果找不到預期的 WAV 文件，記錄到 jump.txt 並繼續下一個
        if not wav_url:
            with open(jump_file, "a", encoding="utf-8") as f:
                f.write(f"跳過：大輪 {current_folder[:2]} 小輪 {page_counter:02d}\n")
            logging.info(f"找不到音檔 {current_folder[:2]}_{page_counter:02d}.wav，跳過")
            return True, file_counter

        # 獲取羅馬拼音和中文
        ab = driver.find_element(By.CSS_SELECTOR, "div#vo-show-ab").text.strip()
        ch = driver.find_element(By.CSS_SELECTOR, "div#vo-show-ch").text.strip()
        
        if not ab or not ch:
            with open(jump_file, "a", encoding="utf-8") as f:
                f.write(f"跳過（內容為空）：大輪 {current_folder[:2]} 小輪 {page_counter:02d}\n")
            logging.warning("詞表內容為空")
            return True, file_counter

        # 清理文字
        ch_clean = clean_text(ch)
        ab_clean = clean_romaji(ab)  # 保留原有的 clean_romaji 函數
        
        # 下載 WAV 文件
        try:
            response = requests.get(wav_url)
            if response.status_code == 200:
                # 生成檔案名稱 (例如: 0001.mp3)
                mp3_name = f"{file_counter:04d}.mp3"
                mp3_path = os.path.join(audio_folder, mp3_name)

                # 轉換並保存為 MP3
                if convert_wav_to_mp3(response.content, mp3_path):
                    with open(label_file, "a", encoding="utf-8") as f:
                        f.write(f"{mp3_name}\n{ch_clean}({ab_clean})\nmale\none\n\n")
                    logging.info(f"已爬取 {wav_url} 並保存為 {mp3_name}: {ch_clean}({ab_clean})")
                    return True, file_counter + 1
                else:
                    logging.error(f"音檔轉換失敗: {wav_url}")
                    return False, file_counter
            else:
                logging.error(f"下載 WAV 文件失敗: {response.status_code}")
                return False, file_counter
        except Exception as e:
            logging.error(f"處理音檔時出錯: {e}")
            return False, file_counter
            
    except Exception as e:
        logging.error(f"處理詞表頁面時出錯: {e}")
        return False, file_counter

def get_next_folder_name(driver, number):
    """獲取指定編號大輪的資料夾名稱"""
    try:
        # 找到對應編號的 div 元素
        selector = f'div.vo-cate[data-value^="{number:02d}"]'
        folder_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return folder_div.get_attribute("data-value")
    except Exception as e:
        logging.error(f"無法獲取第 {number:02d} 大輪的資料夾名稱: {e}")
        return None

def setup_folder_structure(root_folder, folder_name):
    """創建資料夾結構"""
    try:
        # 創建大輪資料夾
        topic_folder = os.path.join(root_folder, f"{folder_name}-10")
        os.makedirs(topic_folder, exist_ok=True)
        
        # 創建音檔資料夾
        audio_folder = os.path.join(topic_folder, "audio")
        os.makedirs(audio_folder, exist_ok=True)
        
        # 創建並初始化 label.txt
        label_file = os.path.join(topic_folder, "label.txt")
        with open(label_file, "w", encoding="utf-8") as f:
            f.write("")
            
        logging.info(f"創建資料夾結構: {topic_folder}")
        return topic_folder, audio_folder, label_file
    except Exception as e:
        logging.error(f"創建資料夾結構失敗: {e}")
        return None, None, None

def crawl_vocabulary(driver, main_lang, dialect, folder_name, start_number=32):
    """爬取學習詞表內容"""
    base_url = "https://web.klokah.tw/vocabulary/"
    driver.get(base_url)
    time.sleep(2)
    
    # 創建學習詞表根目錄
    root_folder = os.path.join(main_lang, dialect, folder_name)
    os.makedirs(root_folder, exist_ok=True)
    logging.info(f"創建根目錄: {root_folder}")
    
    # 創建跳過記錄文件在根目錄
    jump_file = os.path.join(root_folder, "jump.txt")
    if not os.path.exists(jump_file):
        with open(jump_file, "w", encoding="utf-8") as f:
            f.write("")
    
    current_number = start_number  # 使用傳入的起始編號
    while True:  # 大輪迴圈
        try:
            # 在點擊之前先獲取資料夾名稱
            current_folder = get_next_folder_name(driver, current_number)
            if not current_folder:
                logging.info("找不到下一個大輪，結束爬取")
                break
            
            logging.info(f"準備處理大輪: {current_folder}")
            
            # 創建資料夾結構
            topic_folder, audio_folder, label_file = setup_folder_structure(root_folder, current_folder)
            if not topic_folder:
                break
                
            # 點擊大輪圖片
            img_selector = f"img[src*='{current_number:02d}.png']"
            img = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, img_selector))
            )
            img.click()
            time.sleep(2)
            logging.info(f"點擊第 {current_number:02d} 大輪圖片")
            
            # 處理小輪
            page_counter = 1
            file_counter = 1
            
            while True:  # 小輪迴圈
                logging.info(f"處理小輪: {page_counter:02d}")
                driver.requests.clear()
                
                success, file_counter = process_vocabulary_page(
                    driver, audio_folder, label_file, jump_file,
                    current_folder, page_counter, file_counter
                )
                
                if not success:
                    logging.error(f"處理小輪 {page_counter:02d} 失敗")
                    break
                    
                # 檢查下一頁按鈕
                next_btn = driver.find_element(By.CSS_SELECTOR, "button#vo-right")
                if next_btn.get_attribute("style") and "hidden" in next_btn.get_attribute("style"):
                    logging.info(f"當前大輪 {current_folder} 的所有小輪處理完成")
                    break
                    
                next_btn.click()
                time.sleep(1.5)
                page_counter += 1
            
            # 返回主頁面
            back_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button#vo-back"))
            )
            back_btn.click()
            time.sleep(1.5)
            logging.info("返回主頁面")
            
            # 準備處理下一個大輪
            current_number += 1
                
        except Exception as e:
            logging.error(f"處理大輪時出錯: {e}")
            break 