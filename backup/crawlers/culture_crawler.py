#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from crawlers.utils import download_audio, save_label, clean_romaji

def switch_to_tab(driver, tab_name, max_retries=3):
    """嘗試切換到指定的頁籤，如果失敗會重試幾次"""
    try:
        # 先檢查是否已經在目標頁籤
        current_tab = driver.find_element(By.CSS_SELECTOR, f"a.selected[href*='{tab_name}']")
        if current_tab:
            logging.info(f"已經在 [{tab_name}] 頁籤，無需切換")
            return True
    except NoSuchElementException:
        # 如果找不到當前選中的頁籤，則嘗試切換
        for attempt in range(max_retries):
            try:
                # 先等待頁籤出現並可點擊
                tab = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(),'{tab_name}')]"))
                )
                # 確保頁籤在視圖中
                driver.execute_script("arguments[0].scrollIntoView(true);", tab)
                time.sleep(0.5)
                # 嘗試點擊
                tab.click()
                time.sleep(2)
                return True
            except (TimeoutException, ElementClickInterceptedException) as e:
                if attempt == max_retries - 1:
                    logging.error(f"[{tab_name}] 切換失敗 (重試{max_retries}次後): {str(e)}")
                    return False
                logging.warning(f"[{tab_name}] 切換失敗，重試第{attempt + 1}次")
                time.sleep(2)
    return False

def wait_for_vocabulary_content(driver, timeout=10):
    """等待單字頁面的內容完全加載"""
    try:
        # 等待阿美語文字出現
        ab = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.wrapper.view_vocabulary > div.Ab"))
        )
        # 等待中文翻譯出現
        ch = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.wrapper.view_vocabulary > div.Ch"))
        )
        # 等待播放按鈕出現
        play_btn = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.audio_1"))
        )
        # 確保內容不為空
        if not ab.text.strip() or not ch.text.strip():
            time.sleep(1)  # 額外等待以確保內容加載
            if not ab.text.strip() or not ch.text.strip():
                return False
        return True
    except Exception as e:
        logging.warning(f"等待單字內容超時: {e}")
        return False

def verify_audio_download(mp3_url, mp3_name, audio_folder, max_retries=3):
    """驗證音檔是否成功下載，如果失敗則重試"""
    for attempt in range(max_retries):
        try:
            download_audio(mp3_url, mp3_name, audio_folder)
            audio_path = os.path.join(audio_folder, mp3_name)
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                return True
            else:
                logging.warning(f"音檔下載可能不完整，重試第{attempt + 1}次: {mp3_name}")
                time.sleep(1)
        except Exception as e:
            if attempt == max_retries - 1:
                logging.error(f"音檔下載失敗 (重試{max_retries}次後): {mp3_name}, {str(e)}")
                return False
            logging.warning(f"音檔下載失敗，重試第{attempt + 1}次: {mp3_name}")
            time.sleep(1)
    return False

# 文化篇主流程
def crawl_culture(driver, main_lang, dialect, folder_name):
    # 先建立主題資料夾和 -10 子資料夾
    base_folder = os.path.join(main_lang, dialect, folder_name)
    topic_folder = os.path.join(base_folder, f"{folder_name}-10")
    os.makedirs(topic_folder, exist_ok=True)
    audio_folder = os.path.join(topic_folder, "audio")
    os.makedirs(audio_folder, exist_ok=True)
    label_file = os.path.join(topic_folder, "label.txt")
    base_url = 'https://web.klokah.tw/extension/cu_practice/'
    driver.get(base_url)
    time.sleep(2)
    
    # 點首頁圖片
    try:
        img_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "img.no[src*='cu_image/1.png']"))
        )
        img_btn.click()
        time.sleep(2)
    except Exception as e:
        logging.error(f"找不到進入圖片: {e}")
        return

    counter = [1]
    with open(label_file, "w", encoding="utf-8") as label_f:
        round_idx = 1
        while True:
            logging.info(f"=== 開始第 {round_idx} 大輪 ===")
            
            # 1. 確保在文章頁
            if not switch_to_tab(driver, "文章"):
                break
            
            # 處理所有文章段落
            try:
                # 切換到 iframe
                WebDriverWait(driver, 10).until(
                    EC.frame_to_be_available_and_switch_to_it((By.ID, "text-frame"))
                )
                
                # 等待文章內容載入
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div#read-main > div"))
                )
                
                articles = driver.find_elements(By.CSS_SELECTOR, "div#read-main > div")
                for block in articles:
                    try:
                        play_btn = block.find_element(By.CSS_SELECTOR, "button.read-play-btn")
                        mp3_name = f"{counter[0]:04d}.mp3"
                        # 羅馬拼音：只抓 div.read-sentence.Ab > div.word
                        ab_words = block.find_elements(By.CSS_SELECTOR, "div.read-sentence.Ab > div.word")
                        romaji = " ".join([w.text.strip() for w in ab_words if w.text.strip()]).strip()
                        romaji_clean = clean_romaji(romaji)
                        # 中文：抓同一區塊內的 div.read-sentence.Ch
                        try:
                            ch_div = block.find_element(By.CSS_SELECTOR, "div.read-sentence.Ch")
                            chinese = ch_div.get_attribute('textContent').strip()
                        except Exception:
                            chinese = ""
                            
                        driver.requests.clear()
                        play_btn.click()
                        time.sleep(1.5)
                        # mp3 攔截
                        mp3_url = None
                        for req in driver.requests:
                            if req.response and req.url.endswith('.mp3'):
                                mp3_url = req.url
                                break
                        
                        if mp3_url and verify_audio_download(mp3_url, mp3_name, audio_folder):
                            if chinese:
                                label_f.write(f"{mp3_name}\n{chinese}({romaji_clean})\nmale\none\n\n")
                            else:
                                label_f.write(f"{mp3_name}\n({romaji_clean})\nmale\none\n\n")
                            logging.info(f"[文章] 已爬取: {mp3_name} {chinese}({romaji_clean})")
                            counter[0] += 1
                        else:
                            logging.error(f"[文章] 音檔下載失敗: {mp3_name}")
                    except Exception as e:
                        logging.warning(f"[文章] 解析失敗: {e}")
                
                # 切回主頁面
                driver.switch_to.default_content()
                
            except Exception as e:
                logging.error(f"[文章] 區塊解析失敗: {e}")
                # 確保切回主頁面
                try:
                    driver.switch_to.default_content()
                except:
                    pass
            
            # 2. 切換到單詞頁
            if not switch_to_tab(driver, "單詞"):
                break
                
            # 處理所有單詞
            while True:
                try:
                    # 等待單字內容完全加載
                    if not wait_for_vocabulary_content(driver):
                        logging.error("單字內容加載失敗，跳過此單字")
                        break
                        
                    ab = driver.find_element(By.CSS_SELECTOR, "div.wrapper.view_vocabulary > div.Ab").get_attribute("textContent").strip()
                    ab_clean = clean_romaji(ab)
                    ch = driver.find_element(By.CSS_SELECTOR, "div.wrapper.view_vocabulary > div.Ch").get_attribute("textContent").strip()
                    play_btn = driver.find_element(By.CSS_SELECTOR, "a.audio_1")
                    mp3_name = f"{counter[0]:04d}.mp3"
                    
                    if not ab.strip() or not ch.strip():
                        logging.warning(f"單字內容為空，重試: Ab='{ab}', Ch='{ch}'")
                        time.sleep(1)
                        continue
                        
                    driver.requests.clear()
                    play_btn.click()
                    time.sleep(1.2)
                    mp3_url = None
                    for req in driver.requests:
                        if req.response and req.url.endswith('.mp3'):
                            mp3_url = req.url
                            break
                            
                    if mp3_url and verify_audio_download(mp3_url, mp3_name, audio_folder):
                        label_f.write(f"{mp3_name}\n{ch}({ab_clean})\nmale\none\n\n")
                        logging.info(f"[單詞] 已爬取: {mp3_name} {ch}({ab_clean})")
                        counter[0] += 1
                    else:
                        logging.error(f"[單詞] 音檔下載失敗: {mp3_name}")
                        
                except Exception as e:
                    logging.warning(f"[單詞] 解析失敗: {e}")
                    
                # 檢查下一個單詞按鈕
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, "div.next_1")
                    if next_btn.get_attribute("style") and "hidden" in next_btn.get_attribute("style"):
                        break
                    next_btn.click()
                    time.sleep(1.5)  # 增加等待時間，確保新內容加載
                except Exception:
                    break
                    
            # 3. 回到文章頁
            if not switch_to_tab(driver, "文章"):
                break
                
            # 4. 檢查有沒有下一大輪
            try:
                next_a = driver.find_element(By.CSS_SELECTOR, "a.next_1")
                if "hidden" in next_a.get_attribute("class"):
                    break
                next_a.click()
                time.sleep(2)
                round_idx += 1
            except Exception:
                break 