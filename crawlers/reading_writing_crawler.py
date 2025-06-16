import os
import time
import requests
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def download_mp3_from_network(driver, audio_folder, mp3_name):
    # 從 network 請求中下載最新的 mp3 檔案
    for request in reversed(driver.requests):
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
            break

def clean_romaji(romaji):
    # 移除所有括號及其內容
    return re.sub(r'\([^\)]*\)', '', romaji).strip()

def crawl_article_tab(driver, audio_folder, label_file, counter):
    # 進入 iframe
    WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "text-frame")))
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
            # 先清空 network 請求
            driver.requests.clear()
            # 點擊播放按鈕
            play_btn.click()
            time.sleep(1.5)
            # 從 network 下載 mp3
            download_mp3_from_network(driver, audio_folder, mp3_name)
            # 寫入 label.txt
            if chinese:
                label_file.write(f"{mp3_name}\n{chinese}({romaji_clean})\nmale\none\n\n")
            else:
                label_file.write(f"{mp3_name}\n({romaji_clean})\nmale\none\n\n")
            print(f"[文章] 已爬取: {mp3_name} {chinese}({romaji_clean})")
            counter[0] += 1
        except Exception as e:
            print(f"[文章] 解析失敗: {e}")
    # 切回主頁面
    driver.switch_to.default_content()

def crawl_word_tab(driver, audio_folder, label_file, counter):
    # 單詞頁，每頁一個單詞，音檔需點按鈕並監控 network
    while True:
        try:
            ab = driver.find_element(By.CSS_SELECTOR, "div.wrapper.view_vocabulary > div.Ab").get_attribute("textContent").strip()
            ab_clean = clean_romaji(ab)
            ch = driver.find_element(By.CSS_SELECTOR, "div.wrapper.view_vocabulary > div.Ch").get_attribute("textContent").strip()
            play_btn = driver.find_element(By.CSS_SELECTOR, "a.audio_1")
            mp3_name = f"{counter[0]:04d}.mp3"
            driver.requests.clear()
            play_btn.click()
            time.sleep(1.2)
            download_mp3_from_network(driver, audio_folder, mp3_name)
            label_file.write(f"{mp3_name}\n{ch}({ab_clean})\nmale\none\n\n")
            print(f"[單詞] 已爬取: {mp3_name} {ch}({ab_clean})")
            counter[0] += 1
        except Exception as e:
            print(f"[單詞] 解析失敗: {e}")
        # 檢查下一個單詞按鈕
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "div.next_1")
            if next_btn.get_attribute("style") and "hidden" in next_btn.get_attribute("style"):
                break
            next_btn.click()
            time.sleep(1.2)
        except Exception:
            break

def go_to_tab(driver, tab_text):
    try:
        tab = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(),'{tab_text}')]"))
        )
        tab.click()
        time.sleep(1.5)
    except Exception as e:
        print(f"[{tab_text}] 無法切換: {e}")

def has_next_round(driver):
    try:
        next_a = driver.find_element(By.CSS_SELECTOR, "a.next_1")
        if "hidden" in next_a.get_attribute("class"):
            return False
        return True
    except Exception:
        return False

def click_next_round(driver):
    try:
        next_a = driver.find_element(By.CSS_SELECTOR, "a.next_1")
        next_a.click()
        time.sleep(2)
    except Exception as e:
        print(f"[大輪] 無法點擊下一大輪: {e}")

def crawl_reading_writing(driver, main_lang, dialect, folder_name):
    base_folder = os.path.join(main_lang, dialect, folder_name)
    audio_folder = os.path.join(base_folder, f"{folder_name}-10", "audio")
    os.makedirs(audio_folder, exist_ok=True)
    label_txt = os.path.join(base_folder, f"{folder_name}-10", "label.txt")

    # 點擊首頁的圖片按鈕進入主題
    try:
        img_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//img[contains(@src, 'rd_image/1.png')]"))
        )
        img_btn.click()
        time.sleep(2)
    except Exception as e:
        print(f"找不到或無法點擊首頁圖片按鈕: {e}")
        return

    counter = [1]
    with open(label_txt, "w", encoding="utf-8") as label_file:
        round_idx = 1
        while True:
            print(f"=== 開始第 {round_idx} 大輪 ===")
            # 1. 文章頁
            go_to_tab(driver, "文章")
            crawl_article_tab(driver, audio_folder, label_file, counter)
            # 2. 單詞頁
            go_to_tab(driver, "單詞")
            crawl_word_tab(driver, audio_folder, label_file, counter)
            # 3. 回到文章頁
            go_to_tab(driver, "文章")
            # 4. 檢查有沒有下一大輪
            if not has_next_round(driver):
                break
            click_next_round(driver)
            round_idx += 1
    print("閱讀書寫篇爬取完成！")