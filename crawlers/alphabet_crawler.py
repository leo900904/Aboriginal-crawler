#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from .state import CREATED_FOLDERS
from .utils import download_audio, save_label
from selenium.webdriver.support.ui import WebDriverWait

def crawl_alphabet_words(driver, main_lang, dialect, folder_name):
    """爬取字母單字。"""
    # 先建立主題資料夾
    topic_folder = os.path.join(main_lang, dialect, folder_name)
    os.makedirs(topic_folder, exist_ok=True)
    # 再建立主題-10子資料夾
    record_folder = os.path.join(topic_folder, f"{folder_name}-10")
    os.makedirs(record_folder, exist_ok=True)
    audio_folder = os.path.join(record_folder, "audio")
    label_txt = os.path.join(record_folder, "label.txt")
    os.makedirs(audio_folder, exist_ok=True)
    CREATED_FOLDERS.add(record_folder)
    
    # 如果 label.txt 不存在，則初始化它
    if not os.path.exists(label_txt):
        with open(label_txt, "w", encoding="utf-8") as f:
            f.write("")
    
    # 根據現有檔案計算計數器
    counter = len([f for f in os.listdir(audio_folder) if f.lower().endswith('.mp3')]) + 1

    while True:
        # 1. 點擊「查看單字」按鈕
        try:
            view_word_btn = driver.find_element(By.CSS_SELECTOR, ".switcher.to_word")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", view_word_btn)
            actions = ActionChains(driver)
            actions.move_to_element(view_word_btn).click().perform()
            logging.info("已點擊「查看單字」按鈕")
            time.sleep(1)
        except Exception as e:
            logging.error(f"點擊「查看單字」按鈕時出錯：{e}")
            break

        # 2. 處理單字
        while True:
            # 獲取單字和中文文字
            try:
                ab_div = driver.find_element(By.CSS_SELECTOR, "div.text > div.Ab")
                ch_div = driver.find_element(By.CSS_SELECTOR, "div.text > div.Ch")
                ab_text = ab_div.text.strip()
                ch_text = ch_div.text.strip()
            except Exception:
                ab_text = ""
                ch_text = ""
                
            logging.info(f"目前單字：{ab_text}, 中文：{ch_text}")
            
            if ab_text and ch_text:
                label_line = f"{ch_text}({ab_text})"
                mp3_name = str(counter).zfill(4) + ".mp3"
                try:
                    audio_tag = driver.find_element(By.CSS_SELECTOR, "a.sm2_button.audio")
                    audio_url = audio_tag.get_attribute("href")
                    download_audio(audio_url, mp3_name, audio_folder)
                    with open(label_txt, "a", encoding="utf-8") as f:
                        f.write(mp3_name + "\n")
                        f.write(label_line + "\n")
                        f.write("male\n")
                        f.write("one\n")
                        f.write("\n")
                    counter += 1
                except Exception as e:
                    logging.warning(f"找不到或下載音檔失敗：{e}")

            # 檢查「下一頁」按鈕
            try:
                next_btn = driver.find_element(By.XPATH, '//*[@id="main"]/div[4]/div[3]/div[2]/div/div[2]/div[3]/div[2]')
                if not next_btn.is_displayed():
                    logging.info("已到達單字頁面最後一頁")
                    # 點擊「返回字母」
                    try:
                        back_btn = driver.find_element(By.CSS_SELECTOR, "a.switcher.to_alphabet")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", back_btn)
                        actions.move_to_element(back_btn).click().perform()
                        logging.info("已點擊「返回字母」按鈕")
                        time.sleep(1)
                    except Exception as e:
                        logging.error(f"點擊「返回字母」按鈕時出錯：{e}")
                    break
            except Exception:
                logging.info("已到達單字頁面最後一頁")
                # 點擊「返回字母」
                try:
                    back_btn = driver.find_element(By.CSS_SELECTOR, "a.switcher.to_alphabet")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", back_btn)
                    actions.move_to_element(back_btn).click().perform()
                    logging.info("已點擊「返回字母」按鈕")
                    time.sleep(1)
                except Exception as e:
                    logging.error(f"點擊「返回字母」按鈕時出錯：{e}")
                break

            # 點擊「下一頁」按鈕
            old_word = ab_text
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                time.sleep(0.2)
                rect = driver.execute_script("return arguments[0].getBoundingClientRect();", next_btn)
                center_x = int(rect['left'] + rect['width']/2)
                center_y = int(rect['top'] + rect['height']/2)
                covering = driver.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", center_x, center_y)
                if covering != next_btn:
                    logging.warning("按鈕被遮擋，無法點擊")
                    time.sleep(1)
                    continue
                actions.move_to_element(next_btn).click().perform()
                time.sleep(0.3)
                try:
                    WebDriverWait(driver, 5).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "div.text > div.Ab").text.strip() != old_word
                    )
                    time.sleep(0.5)
                except Exception:
                    driver.execute_script("""
                    arguments[0].dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                    arguments[0].dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                    arguments[0].dispatchEvent(new MouseEvent('click', {bubbles:true}));
                    """, next_btn)
                    try:
                        WebDriverWait(driver, 5).until(
                            lambda d: d.find_element(By.CSS_SELECTOR, "div.text > div.Ab").text.strip() != old_word
                        )
                        time.sleep(0.5)
                    except Exception:
                        logging.warning("等待新單字超時，嘗試下一頁")
                        continue
            except Exception as e:
                logging.error(f"下一頁按鈕出錯：{e.__class__.__name__}: {e}")
                driver.save_screenshot('next_error.png')
                time.sleep(1)
                continue

        # 返回字母頁面，嘗試點擊「下一頁」
        try:
            next_alpha_btn = driver.find_element(By.XPATH, '//*[@id="main"]/div[4]/div[3]/div[1]/div[2]/div[2]')
            if not next_alpha_btn.is_displayed():
                logging.info("已到達字母頁面最後一頁")
                break
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_alpha_btn)
            actions.move_to_element(next_alpha_btn).click().perform()
            logging.info("已點擊字母頁面下一頁按鈕")
            time.sleep(1)
        except Exception as e:
            logging.error(f"字母頁面下一頁按鈕出錯或已到最後一頁：{e}")
            break 