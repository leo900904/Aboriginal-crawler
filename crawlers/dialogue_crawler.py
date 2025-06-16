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

def clean_text(text):
    """清理文字，移除括號及其內容"""
    cleaned = re.sub(r'\([^)]*\)', '', text)
    return cleaned.strip()

def get_next_folder_name(driver, number):
    """獲取指定編號大輪的資料夾名稱"""
    try:
        # 找到對應編號的圖片元素
        selector = f'img[src*="{number:02d}.png"]'
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
            except Exception:
                continue
    except Exception as e:
        logging.warning(f"找不到 audioSet: {e}")
    return audio_map

def crawl_dialogue_texts(driver, label_file, audio_folder, start_idx=1):
    label_idx = start_idx
    audio_map = get_audio_mapping(driver)
    season_divs = driver.find_elements(By.CSS_SELECTOR, "div.dia-season-div[style*='display: block']")
    for season_div in season_divs:
        try:
            frame_inner = season_div.find_element(By.CSS_SELECTOR, "div[class^='dia-frame-'][class$='-inner']")
            sections = frame_inner.find_elements(By.CSS_SELECTOR, "div.section")
            all_items = []
            for section in sections:
                items = section.find_elements(By.XPATH, './div')
                for item in items:
                    try:
                        num = int(item.find_element(By.CSS_SELECTOR, ".dia-num").text.strip())
                    except Exception:
                        num = 9999
                    all_items.append((num, item))
            all_items.sort(key=lambda x: x[0])
            for num, item in all_items:
                try:
                    ab = item.find_element(By.CSS_SELECTOR, ".dia-show-ab").text.strip()
                except Exception:
                    ab = ""
                try:
                    ch = item.find_element(By.CSS_SELECTOR, ".dia-show-ch").text.strip()
                except Exception:
                    ch = ""
                try:
                    data_value = item.find_element(By.CSS_SELECTOR, ".dia-sound").get_attribute("data-value")
                except Exception:
                    data_value = None
                mp3_name = f"{label_idx:04d}.mp3"
                if data_value and data_value in audio_map:
                    audio_src = audio_map[data_value]
                    download_audio(audio_src, mp3_name, audio_folder)
                else:
                    print(f"找不到音檔 data-value: {data_value}")
                # clean 文字
                ab_clean = clean_text(ab)
                ch_clean = clean_text(ch)
                with open(label_file, "a", encoding="utf-8") as f:
                    f.write(f"{mp3_name}\n{ch_clean}({ab_clean})\nmale\none\n\n")
                label_idx += 1
        except Exception as e:
            print(f"解析失敗: {e}")
            continue
    return label_idx

def crawl_all_season_dialogues(driver, label_file, audio_folder, label_idx):
    for season_idx in [1, 2, 3]:
        try:
            season_btn = driver.find_element(By.ID, f"dia-season-{season_idx}")
            if not season_btn.is_displayed():
                continue
            season_btn.click()
            time.sleep(1)
        except Exception:
            continue
        try:
            part = driver.find_element(By.ID, f"partTitle-{season_idx}")
            part.click()
            time.sleep(1)
            label_idx = crawl_dialogue_texts(driver, label_file, audio_folder, start_idx=label_idx)
            time.sleep(1)
        except Exception as e:
            print(f"處理 season {season_idx} 對話練習失敗: {e}")
    return label_idx

def crawl_word_practice(driver, audio_folder, label_file, start_idx, original_iframe_src=None):
    label_idx = start_idx
    print(f"開始單詞練習爬取，起始index: {label_idx}")
    
    # 在進入iframe前，先獲取音檔映射
    print("獲取主頁面的audioSet音檔映射...")
    main_audio_map = {}
    try:
        # 切回主頁面獲取audioSet
        driver.switch_to.default_content()
        audio_set = driver.find_element(By.ID, "audioSet")
        audio_tags = audio_set.find_elements(By.CSS_SELECTOR, "audio.player-ab")
        for audio in audio_tags:
            data_value = audio.get_attribute("data-value")
            try:
                source = audio.find_element(By.TAG_NAME, "source")
                src = source.get_attribute("src")
                main_audio_map[data_value] = src
                print(f"音檔映射: {data_value} -> {src}")
            except Exception:
                continue
        print(f"獲取到 {len(main_audio_map)} 個音檔映射")
    except Exception as e:
        print(f"獲取audioSet失敗: {e}")
    
    try:
        print("等待dia-frame-inner容器出現...")
        # 先等待包含iframe的容器變為可見，增加等待時間因為學習三可能需要更長時間
        
        # 嘗試多種方式來找到容器
        container_found = False
        
        # 方法1：尋找 style="display: block" 的 dia-frame-inner
        try:
            print("嘗試方法1：尋找顯示狀態的dia-frame-inner...")
            WebDriverWait(driver, 8).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dia-frame-inner[style*='display: block']"))
            )
            print("方法1成功：找到顯示狀態的dia-frame-inner")
            container_found = True
        except TimeoutException:
            print("方法1失敗，嘗試方法2...")
        
        # 方法2：如果方法1失敗，嘗試找任何 dia-frame-inner
        if not container_found:
            try:
                print("嘗試方法2：尋找任何dia-frame-inner...")
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.dia-frame-inner"))
                )
                print("方法2成功：找到dia-frame-inner")
                container_found = True
            except TimeoutException:
                print("方法2失敗，嘗試方法3...")
        
        # 方法3：如果前兩種方法都失敗，等待更長時間
        if not container_found:
            try:
                print("嘗試方法3：等待更長時間...")
                time.sleep(5)
                container = driver.find_element(By.CSS_SELECTOR, "div.dia-frame-inner")
                print(f"方法3成功：找到container，style: {container.get_attribute('style')}")
                container_found = True
            except Exception as e:
                print(f"方法3失敗: {e}")
        
        if not container_found:
            raise Exception("無法找到dia-frame-inner容器")
        
        print("dia-frame-inner容器已確認存在")
        
        print("等待iframe元素出現...")
        # 使用ID selector來尋找iframe，更加精確
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "dia-frame-show"))
        )
        iframe = driver.find_element(By.ID, "dia-frame-show")
        iframe_src = iframe.get_attribute('src')
        print(f"找到iframe: {iframe_src}")
        
        # 確保iframe載入了正確的內容（不是之前學習的內容）
        if original_iframe_src and original_iframe_src == iframe_src:
            print("檢測到iframe還是之前的內容，等待更新...")
            # 等待iframe src更新
            max_wait = 10
            for i in range(max_wait):
                time.sleep(1)
                iframe = driver.find_element(By.ID, "dia-frame-show")
                iframe_src = iframe.get_attribute('src')
                print(f"等待第{i+1}秒，iframe src: {iframe_src}")
                if original_iframe_src != iframe_src:
                    print("iframe已更新到正確內容")
                    break
            else:
                print("iframe未更新，但繼續嘗試...")
        elif original_iframe_src:
            print("iframe已經是新內容")
        else:
            print("沒有之前的iframe可比較")
        
        # 確保iframe完全載入
        print("等待iframe完全載入...")
        WebDriverWait(driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "dia-frame-show"))
        )
        print("成功切換到iframe")
         
        print("等待iframe內容完全載入...")
        time.sleep(5) # 增加更多緩衝時間，特別是對學習三
        
        # 確保iframe內容完全載入 - 等待body元素完全加載
        try:
            print("確認iframe內容完全載入...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            print("iframe body已載入")
            
            # 等待至少有一些基本元素
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.TAG_NAME, "div")) > 5
            )
            print("iframe內div元素已載入")
            
        except Exception as e:
            print(f"等待iframe內容載入時出錯: {e}")
        
        # 檢查iframe內部的DOM結構
        try:
            print("檢查iframe內部結構...")
            body = driver.find_element(By.TAG_NAME, "body")
            print(f"iframe body已找到")
            
            # 嘗試找所有的div元素
            all_divs = driver.find_elements(By.TAG_NAME, "div")
            print(f"iframe內找到 {len(all_divs)} 個div元素")
            
            # 檢查有沒有任何帶有display: block的div
            block_divs = driver.find_elements(By.CSS_SELECTOR, 'div[style*="display: block"]')
            print(f"找到 {len(block_divs)} 個display:block的div")
            
            if len(block_divs) == 0:
                print("沒有找到display:block的div，等待更長時間...")
                time.sleep(5)
                block_divs = driver.find_elements(By.CSS_SELECTOR, 'div[style*="display: block"]')
                print(f"等待後找到 {len(block_divs)} 個display:block的div")
                
        except Exception as e:
            print(f"檢查iframe結構時出錯: {e}")
        
        print("iframe內容載入完成，開始處理單詞...")
        
        while True:
            print(f"\n--- 處理單詞 {label_idx} ---")
            
            # 只抓顯示中的那一頁
            # 確保每次迴圈都重新找到當前顯示的 block_div，並等待它可見
            print("尋找當前顯示的block_div...")
            
            block_div = None
            try:
                # 方法1：標準方式尋找
                block_div = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'div[style*="display: block"]'))
                )
                print("找到當前顯示的block_div（方法1）")
            except TimeoutException:
                print("方法1失敗，嘗試其他方法...")
                try:
                    # 方法2：先找所有div，然後過濾
                    all_divs = driver.find_elements(By.TAG_NAME, "div")
                    for div in all_divs:
                        style = div.get_attribute("style")
                        if style and "display: block" in style:
                            block_div = div
                            print(f"找到block_div（方法2），style: {style}")
                            break
                    
                    if not block_div:
                        print("方法2也失敗，列出所有div的style屬性...")
                        for i, div in enumerate(all_divs[:10]):  # 只顯示前10個
                            style = div.get_attribute("style")
                            class_name = div.get_attribute("class")
                            print(f"div[{i}] style: '{style}', class: '{class_name}'")
                        
                        raise Exception("無法找到任何display:block的div")
                        
                except Exception as e:
                    print(f"所有方法都失敗: {e}")
                    raise
            
            if not block_div:
                raise Exception("block_div為None")
            
            print(f"找到block_div，class: {block_div.get_attribute('class')}, style: {block_div.get_attribute('style')}")
            
            # 檢查block_div內部結構
            print("檢查block_div內部元素...")
            try:
                inner_elements = block_div.find_elements(By.TAG_NAME, "*")
                print(f"block_div內有 {len(inner_elements)} 個子元素")
                
                # 列出前幾個元素的信息
                for i, elem in enumerate(inner_elements[:5]):
                    tag = elem.tag_name
                    class_name = elem.get_attribute('class')
                    text = elem.text[:20] if elem.text else ""
                    print(f"  元素[{i}]: <{tag}> class='{class_name}' text='{text}...'")
                    
                # 檢查是否有.word元素
                word_elements = block_div.find_elements(By.CSS_SELECTOR, ".word")
                print(f"block_div內找到 {len(word_elements)} 個.word元素")
                
                if len(word_elements) == 0:
                    print("沒有找到.word元素，等待更長時間...")
                    time.sleep(3)
                    word_elements = block_div.find_elements(By.CSS_SELECTOR, ".word")
                    print(f"等待後找到 {len(word_elements)} 個.word元素")
                    
            except Exception as e:
                print(f"檢查block_div內部結構時出錯: {e}")
            
            print("等待word元素可見...")
            word_element = WebDriverWait(block_div, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".word")))
            current_word_data_value = word_element.get_attribute("data-value") # 獲取當前單詞的 data-value
            print(f"當前單詞data-value: {current_word_data_value}")

            ab = word_element.text.strip() # 直接從已找到的 word_element 獲取文本
            print(f"獲取到羅馬拼音/注音: '{ab}'")
            ch = ""

            try:
                print("嘗試點擊顯示中文按鈕...")
                # 確保按鈕可點擊再點擊，並直接獲取可點擊的元素
                ch_btn = WebDriverWait(block_div, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".read-chinese-btn")))
                ch_btn.click()
                print("成功點擊中文按鈕")
                time.sleep(0.2)
            except Exception as e:
                print(f"點擊中文按鈕失敗: {e}")

            try:
                ch = block_div.find_element(By.CSS_SELECTOR, ".read-sentence.Ch").text.strip()
                print(f"獲取到中文: '{ch}'")
            except Exception as e:
                print(f"獲取中文失敗: {e}")

            try:
                print("嘗試點擊播放按鈕...")
                # 確保播放按鈕可點擊再點擊，並直接獲取可點擊的元素
                play_btn = WebDriverWait(block_div, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".read-play-btn")))
                
                # 從播放按鈕獲取data-value
                play_data_value = play_btn.get_attribute("data-value")
                print(f"播放按鈕data-value: {play_data_value}")
                
                mp3_name = f"{label_idx:04d}.mp3"
                mp3_url = None
                
                # 使用audioSet映射獲取音檔URL
                if play_data_value and play_data_value in main_audio_map:
                    mp3_url = main_audio_map[play_data_value]
                    print(f"從audioSet找到音檔URL: {mp3_url}")
                    download_audio(mp3_url, mp3_name, audio_folder)
                    print(f"音檔下載完成: {mp3_name}")
                else:
                    print(f"未在audioSet中找到data-value: {play_data_value}")
                    # 備用方案：點擊播放按鈕並監控network
                    print("使用備用方案：監控network請求...")
                    driver.requests.clear()
                    play_btn.click()
                    time.sleep(1.2)
                    
                    for req in driver.requests:
                        if req.response and req.url.endswith('.mp3'):
                            mp3_url = req.url
                            print(f"從network找到mp3 URL: {mp3_url}")
                            break
                    
                    if mp3_url:
                        download_audio(mp3_url, mp3_name, audio_folder)
                        print(f"音檔下載完成: {mp3_name}")
                        
            except Exception as e:
                print(f"下載音檔失敗: {e}")
                mp3_name = f"{label_idx:04d}.mp3" # 即使下載失敗也要確保檔名正確
            
            ab_clean = clean_text(ab)
            ch_clean = clean_text(ch)
            print(f"清理後文字 - 羅馬拼音: '{ab_clean}', 中文: '{ch_clean}'")
            
            with open(label_file, "a", encoding="utf-8") as f:
                f.write(f"{mp3_name}\n{ch_clean}({ab_clean})\nmale\none\n\n")
            print(f"寫入label檔案: {mp3_name} - {ch_clean}({ab_clean})")
            label_idx += 1
            
            # 點擊下一個
            try:
                print("尋找下一個按鈕...")
                # 使用 WebDriverWait 確保 next_btn 存在且可點擊
                next_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "read-arrow-right"))
                )
                
                button_style = next_btn.get_attribute("style")
                print(f"下一個按鈕初始樣式: {button_style}")
                
                if "visibility: hidden" in button_style or "display: none" in button_style:
                    print("下一個按鈕已隱藏，結束循環")
                    break
                
                print("點擊下一個按鈕...")
                next_btn.click()
                
                print("等待新單詞載入...")
                # 等待新的單詞內容載入，改為檢查單詞文本是否改變，而不僅僅是 data-value
                try:
                    current_word_text = word_element.text.strip()  # 記錄當前單詞文本
                    print(f"當前單詞文本: '{current_word_text}'，等待變化...")
                    
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, 'div[style*="display: block"] .word').text.strip() != current_word_text
                    )
                    print("新單詞已載入（基於文本變化）")
                except TimeoutException:
                    print("等待新單詞載入超時，檢查是否到達最後一個單詞...")
                    # 檢查是否下一個按鈕變為隱藏（表示已到最後一個）
                    try:
                        next_btn_check = driver.find_element(By.ID, "read-arrow-right")
                        next_btn_style = next_btn_check.get_attribute("style")
                        print(f"下一個按鈕樣式: {next_btn_style}")
                        
                        if "visibility: hidden" in next_btn_style or "display: none" in next_btn_style:
                            print("確認已到達最後一個單詞，結束循環")
                            break
                        else:
                            print("下一個按鈕仍可見，可能是載入問題，繼續嘗試...")
                            time.sleep(3)  # 給更多時間
                            # 再次檢查是否有新的單詞載入（基於文本變化）
                            try:
                                new_word_text = driver.find_element(By.CSS_SELECTOR, 'div[style*="display: block"] .word').text.strip()
                                print(f"延遲檢查 - 當前單詞文本: '{new_word_text}'")
                                if new_word_text != current_word_text:
                                    print("新單詞已載入（延遲檢查成功，基於文本變化）")
                                else:
                                    print("仍未檢測到新單詞，可能真的到達最後一個，結束循環")
                                    break
                            except Exception as e:
                                print(f"檢查新單詞時出錯: {e}，結束循環")
                                break
                    except Exception as e:
                        print(f"檢查下一個按鈕狀態時出錯: {e}，結束循環")
                        break

                time.sleep(0.5)
            except Exception as e:
                print(f"導航到下一個單詞失敗: {e}")
                break
        
        print("離開iframe...")
        driver.switch_to.default_content() # 離開 iframe
        print("成功離開iframe")
        
    except Exception as e:
        print(f"單詞練習解析失敗: {e}")
        driver.switch_to.default_content() # 確保離開 iframe
        
    print(f"單詞練習爬取完成，最終index: {label_idx}")
    return label_idx

def try_crawl_word_practice(driver, audio_folder, label_file, start_idx):
    label_idx = start_idx
    print(f"檢查是否有單詞練習，當前label_idx: {label_idx}")
    
    # 在點擊前記錄當前iframe的src（如果存在）
    original_iframe_src = None
    try:
        existing_iframe = driver.find_element(By.ID, "dia-frame-show")
        original_iframe_src = existing_iframe.get_attribute('src')
        print(f"點擊前iframe src: {original_iframe_src}")
    except Exception:
        print("點擊前未找到iframe")
    
    try:
        part_titles = driver.find_elements(By.CSS_SELECTOR, ".partTitle")
        print(f"找到 {len(part_titles)} 個 partTitle 元素")
        
        for i, part in enumerate(part_titles):
            try:
                part_text = part.text
                print(f"partTitle[{i}]: '{part_text}'")
                
                if "單詞練習" in part_text:
                    print(f"找到單詞練習按鈕: '{part_text}'")
                    print("點擊單詞練習按鈕...")
                    part.click()
                    print("等待頁面內容載入...")
                    time.sleep(3)  # 增加等待時間，特別是對學習三
                    print("成功點擊單詞練習按鈕，開始爬取...")
                    label_idx = crawl_word_practice(driver, audio_folder, label_file, label_idx, original_iframe_src)
                    print(f"單詞練習爬取完成，返回label_idx: {label_idx}")
                    break
            except Exception as e:
                print(f"處理partTitle[{i}]時出錯: {e}")
                continue
    except Exception as e:
        print(f"檢查單詞練習失敗: {e}")
    
    print(f"try_crawl_word_practice 完成，最終label_idx: {label_idx}")
    return label_idx

def crawl_dialogue(driver, main_lang, dialect, folder_name):
    """爬取情境族語內容"""
    base_url = "https://web.klokah.tw/dialogue/"
    driver.get(base_url)
    time.sleep(2)
    
    root_folder = os.path.join(main_lang, dialect, folder_name)
    os.makedirs(root_folder, exist_ok=True)
    logging.info(f"創建根目錄: {root_folder}")
    
    jump_file = os.path.join(root_folder, "jump.txt")
    if not os.path.exists(jump_file):
        with open(jump_file, "w", encoding="utf-8") as f:
            f.write("")
    
    current_number = 1
    while True:
        try:
            current_folder = get_next_folder_name(driver, current_number)
            if not current_folder:
                logging.info("找不到下一個大輪，結束爬取")
                break
            logging.info(f"準備處理大輪: {current_folder}")
            topic_folder, audio_folder, label_file = setup_folder_structure(root_folder, current_folder)
            if not topic_folder:
                break
            print(f"清空前 network 請求數量: {len(driver.requests)}")
            driver.requests.clear()
            print(f"清空後 network 請求數量: {len(driver.requests)}")
            img_selector = f"img[src*='{current_number:02d}.png']"
            img = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, img_selector))
            )
            img.click()
            time.sleep(2)
            logging.info(f"點擊第 {current_number:02d} 大輪圖片")
            time.sleep(1)
            label_idx = 1
            label_idx = crawl_all_season_dialogues(driver, label_file, audio_folder, label_idx)
            # 對話練習都爬完後，檢查學習二、三的單詞練習，label_idx 接續
            for season_idx in [2, 3]:
                try:
                    season_btn = driver.find_element(By.ID, f"dia-season-{season_idx}")
                    if not season_btn.is_displayed():
                        continue
                    season_btn.click()
                    time.sleep(1)
                    label_idx = try_crawl_word_practice(driver, audio_folder, label_file, label_idx)
                except Exception:
                    continue
            back_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button#dia-back"))
            )
            back_btn.click()
            time.sleep(1.5)
            logging.info("返回主頁面")
            current_number += 1
        except Exception as e:
            logging.error(f"處理大輪時出錯: {e}")
            break 