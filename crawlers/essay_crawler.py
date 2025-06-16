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

def clean_text(text):
    """清理文字，移除括號及其內容"""
    cleaned = re.sub(r'\([^)]*\)', '', text)
    return cleaned.strip()

def get_next_folder_name(driver, number):
    """獲取指定編號大輪的資料夾名稱"""
    try:
        # 找到對應編號的圖片元素，使用更精確的選擇器
        selector = f'img[src="img/{number:02d}.png"]'
        img = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return img.get_attribute("data-value")
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

def get_audio_mapping(driver):
    """獲取音檔映射"""
    audio_map = {}
    try:
        audio_set = driver.find_element(By.ID, "audioSet")
        audio_tags = audio_set.find_elements(By.CSS_SELECTOR, "audio.player-ab")
        for audio in audio_tags:
            data_value = audio.get_attribute("data-value")
            try:
                source = audio.find_element(By.TAG_NAME, "source")
                src = source.get_attribute("src")
                audio_map[data_value] = src
                logging.info(f"音檔映射: {data_value} -> {src}")
            except Exception:
                continue
    except Exception as e:
        logging.warning(f"找不到 audioSet: {e}")
    return audio_map

def detect_level_type(driver):
    """檢測級別類型：初中級或中高級"""
    try:
        # 檢查是否有 lv-e (初級) 或 lv-m (中級) 
        try:
            driver.find_element(By.CSS_SELECTOR, "div.level_label.lv-e")
            return "elementary_middle"
        except:
            pass
        
        try:
            driver.find_element(By.CSS_SELECTOR, "div.level_label.lv-m")
            return "elementary_middle"
        except:
            pass
        
        # 檢查是否有 lv-mh (中高級)
        try:
            driver.find_element(By.CSS_SELECTOR, "div.level_label.lv-mh")
            return "middle_high"
        except:
            pass
            
    except Exception as e:
        logging.warning(f"檢測級別類型失敗: {e}")
    
    return "unknown"

def crawl_elementary_middle_level(driver, audio_folder, label_file, start_idx, audio_map):
    """爬取初、中級內容"""
    label_idx = start_idx
    logging.info("開始爬取初、中級內容")

    while True:
        try:
            # 找到當前顯示的section
            logging.info("尋找當前顯示的section...")
            current_section = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.esa-learn-section.slide[style*="display: block"]'))
            )
            logging.info("找到當前顯示的section")
            
            # 在當前section中找播放按鈕（不需要點擊，音檔已經加載了）
            logging.info("在當前section中尋找播放按鈕...")
            play_btn = current_section.find_element(By.CSS_SELECTOR, "button.esa-sound")
            data_value = play_btn.get_attribute("data-value")
            logging.info(f"找到播放按鈕，data-value: {data_value}（音檔已預加載，無需點擊）")
            
            # 在當前section中提取文字內容
            logging.info("在當前section中提取文字內容...")
            sentence_element = current_section.find_element(By.CSS_SELECTOR, "div.esa-learn-sentence")
            sentence_divs = sentence_element.find_elements(By.TAG_NAME, "div")
            
            aboriginal_text = ""
            chinese_text = ""
            
            if len(sentence_divs) >= 2:
                aboriginal_text = sentence_divs[0].text.strip()
                chinese_text = sentence_divs[1].text.strip()
                logging.info(f"提取到文字 - 族語: '{aboriginal_text}', 中文: '{chinese_text}'")
            else:
                logging.warning(f"文字提取異常，只找到 {len(sentence_divs)} 個div元素")
            
            # 生成音檔名稱
            mp3_name = f"{label_idx:04d}.mp3"
            
            # 從audio mapping下載音檔（音檔已經在進入學習時預加載了）
            if data_value and data_value in audio_map:
                audio_src = audio_map[data_value]
                download_audio(audio_src, mp3_name, audio_folder)
                logging.info(f"從audioSet下載音檔: {mp3_name}")
            else:
                logging.warning(f"找不到音檔 data-value: {data_value}")
            
            # 清理文字
            aboriginal_clean = clean_text(aboriginal_text)
            chinese_clean = clean_text(chinese_text)
            
            # 儲存文字
            combined_text = f"{chinese_clean}({aboriginal_clean})"
            with open(label_file, "a", encoding="utf-8") as f:
                f.write(f"{mp3_name}\n{combined_text}\nmale\none\n\n")
            
            logging.info(f"處理完成: {combined_text}")
            label_idx += 1
            
            # 檢查下一個按鈕
            right_btn = driver.find_element(By.ID, "esa-right")
            style = right_btn.get_attribute("style")
            
            if "visibility: hidden" in style or "display: none" in style:
                logging.info("下一個按鈕已隱藏，結束爬取")
                break
            
            # 點擊下一個
            logging.info("點擊右箭頭按鈕，進入下一頁")
            right_btn.click()
            
            # 等待新內容載入，檢查顯示的section是否變化
            try:
                # 記錄當前的data-value以檢測變化
                current_data_value = data_value
                logging.info(f"等待新內容載入，當前data-value: {current_data_value}")
                
                # 等待新的section出現且其中的播放按鈕data-value改變
                WebDriverWait(driver, 15).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, 'div.esa-learn-section.slide[style*="display: block"] button.esa-sound').get_attribute("data-value") != current_data_value
                )
                logging.info("新內容已載入")
                time.sleep(1)  # 額外等待確保內容完全載入
                
            except TimeoutException:
                logging.warning("等待新內容載入超時，檢查是否已到最後一頁")
                # 重新檢查右箭頭按鈕狀態
                right_btn_check = driver.find_element(By.ID, "esa-right")
                style_check = right_btn_check.get_attribute("style")
                if "visibility: hidden" in style_check or "display: none" in style_check:
                    logging.info("確認已到最後一頁，結束爬取")
                    break
                else:
                    logging.error("等待新內容載入失敗，但右箭頭仍可見，可能出現未知錯誤")
                    break
            
        except Exception as e:
            logging.error(f"爬取初、中級內容時出錯: {e}")
            break
    
    return label_idx

def crawl_middle_high_level(driver, audio_folder, label_file, start_idx, audio_map):
    """爬取中高級內容"""
    label_idx = start_idx
    logging.info("開始爬取中高級內容")
    
    try:
        # 中高級一次性顯示所有內容，找到所有的section
        logging.info("尋找所有esa-learn-section...")
        all_sections = driver.find_elements(By.CSS_SELECTOR, "div.esa-learn-section")
        logging.info(f"找到 {len(all_sections)} 個section")
        
        # 遍歷每個section來提取內容
        for i, section in enumerate(all_sections):
            try:
                logging.info(f"處理第 {i+1} 個section...")
                
                # 檢查section是否有內容
                try:
                    play_btn = section.find_element(By.CSS_SELECTOR, "button.esa-sound")
                    sentence_element = section.find_element(By.CSS_SELECTOR, "div.esa-learn-sentence")
                except NoSuchElementException:
                    logging.info(f"第 {i+1} 個section沒有播放按鈕或句子，跳過")
                    continue
                
                # 獲取data-value
                data_value = play_btn.get_attribute("data-value")
                logging.info(f"第 {i+1} 個section，data-value: {data_value}")
                
                # 提取文字內容
                sentence_divs = sentence_element.find_elements(By.TAG_NAME, "div")
                
                aboriginal_text = ""
                chinese_text = ""
                
                if len(sentence_divs) >= 2:
                    aboriginal_text = sentence_divs[0].text.strip()
                    chinese_text = sentence_divs[1].text.strip()
                    logging.info(f"提取到文字 - 族語: '{aboriginal_text}', 中文: '{chinese_text}'")
                else:
                    logging.warning(f"第 {i+1} 個section文字提取異常，只找到 {len(sentence_divs)} 個div元素")
                    continue
                
                # 跳過空內容
                if not aboriginal_text and not chinese_text:
                    logging.info(f"第 {i+1} 個section內容為空，跳過")
                    continue
                
                # 生成音檔名稱
                mp3_name = f"{label_idx:04d}.mp3"
                
                # 從audio mapping下載音檔（不需要點擊按鈕，音檔已經加載了）
                audio_downloaded = False
                if data_value and data_value in audio_map:
                    audio_src = audio_map[data_value]
                    download_audio(audio_src, mp3_name, audio_folder)
                    logging.info(f"從audioSet下載音檔: {mp3_name}")
                    audio_downloaded = True
                else:
                    logging.warning(f"第 {i+1} 個section找不到音檔 data-value: {data_value}")
                
                # 清理文字
                aboriginal_clean = clean_text(aboriginal_text)
                chinese_clean = clean_text(chinese_text)
                
                # 儲存文字
                combined_text = f"{chinese_clean}({aboriginal_clean})"
                with open(label_file, "a", encoding="utf-8") as f:
                    f.write(f"{mp3_name}\n{combined_text}\nmale\none\n\n")
                
                logging.info(f"處理完成第 {i+1} 個section: {combined_text}")
                label_idx += 1
                
            except Exception as e:
                logging.error(f"處理第 {i+1} 個section時出錯: {e}")
                continue
                
    except Exception as e:
        logging.error(f"爬取中高級內容時出錯: {e}")
    
    logging.info(f"中高級內容爬取完成，處理了 {label_idx - start_idx} 個句子")
    return label_idx

def crawl_season_content(driver, season_number, audio_folder, label_file, start_idx):
    """爬取指定學習季的內容"""
    label_idx = start_idx
    
    try:
        # 點擊學習按鈕
        season_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, f"esa-season-{season_number}"))
        )
        season_btn.click()
        time.sleep(2)
        
        logging.info(f"開始爬取學習{season_number}")
        
        # 獲取當前學習季的音檔映射（每個學習季獲取一次）
        audio_map = get_audio_mapping(driver)
        logging.info(f"學習{season_number} 獲取到 {len(audio_map)} 個音檔映射")
        
        # 檢測級別類型
        level_type = detect_level_type(driver)
        logging.info(f"檢測到級別類型: {level_type}")
        
        if level_type == "elementary_middle":
            label_idx = crawl_elementary_middle_level(driver, audio_folder, label_file, label_idx, audio_map)
        elif level_type == "middle_high":
            label_idx = crawl_middle_high_level(driver, audio_folder, label_file, label_idx, audio_map)
        else:
            logging.warning(f"未知的級別類型: {level_type}")
        
    except Exception as e:
        logging.error(f"爬取學習{season_number}時出錯: {e}")
    
    return label_idx

def crawl_essay(driver, main_lang, dialect, folder_name):
    """爬取族語短文內容"""
    base_url = "https://web.klokah.tw/essay/"
    driver.get(base_url)
    time.sleep(2)
    
    root_folder = os.path.join(main_lang, dialect, folder_name)
    os.makedirs(root_folder, exist_ok=True)
    logging.info(f"創建根目錄: {root_folder}")
    
    current_number = 1
    
    while True:
        try:
            # 獲取下一個大輪的名稱
            current_folder = get_next_folder_name(driver, current_number)
            if not current_folder:
                logging.info("找不到下一個大輪，結束爬取")
                break
                
            logging.info(f"準備處理大輪: {current_folder}")
            
            # 設置資料夾結構
            topic_folder, audio_folder, label_file = setup_folder_structure(root_folder, current_folder)
            if not topic_folder:
                break
            
            # 清空 network 請求
            driver.requests.clear()
            
            # 點擊大輪圖片
            img_selector = f'img[src="img/{current_number:02d}.png"]'
            img = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, img_selector))
            )
            img.click()
            time.sleep(2)
            logging.info(f"點擊第 {current_number:02d} 大輪圖片")
            
            label_idx = 1
            
            # 爬取學習一和學習二
            for season in [1, 2]:
                try:
                    # 檢查學習按鈕是否存在
                    season_btn = driver.find_element(By.ID, f"esa-season-{season}")
                    if season_btn.is_displayed():
                        label_idx = crawl_season_content(driver, season, audio_folder, label_file, label_idx)
                except Exception as e:
                    logging.error(f"處理學習{season}時出錯: {e}")
                    continue
            
            # 返回主頁面
            try:
                back_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "esa-back"))
                )
                back_btn.click()
                time.sleep(2)
                logging.info("返回主頁面")
            except Exception as e:
                logging.error(f"返回主頁面失敗: {e}")
                
            current_number += 1
            
        except Exception as e:
            logging.error(f"處理大輪時出錯: {e}")
            break
    
    logging.info("族語短文爬取完成") 