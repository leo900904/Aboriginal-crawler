import os
import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

def clean_romaji(romaji):
    return re.sub(r'\([^\)]*\)', '', romaji).strip()

def crawl_scene_and_list(driver, audio_folder, label_file, counter):
    # 1. 先爬 scene 區塊
    scenes = driver.find_elements(By.CSS_SELECTOR, "div.scene")
    for scene in scenes:
        try:
            mp3_url = scene.find_element(By.CSS_SELECTOR, "a.audio_1").get_attribute("href")
            ab_divs = scene.find_elements(By.CSS_SELECTOR, "div.text > div.Ab")
            if ab_divs:
                ab = ab_divs[-1].get_attribute("textContent").strip()
            else:
                ab = ""
            ab_clean = clean_romaji(ab)
            ch = scene.find_element(By.CSS_SELECTOR, "div.text > div.Ch").get_attribute("textContent").strip()
            mp3_name = f"{counter[0]:04d}.mp3"
            resp = requests.get(mp3_url)
            with open(os.path.join(audio_folder, mp3_name), "wb") as f:
                f.write(resp.content)
            label_file.write(f"{mp3_name}\n{ch}({ab_clean})\nmale\none\n\n")
            print(f"[會話] 已爬取: {mp3_name} {ch}({ab_clean})")
            counter[0] += 1
        except Exception as e:
            print(f"[scene] 解析失敗: {e}")
    # 2. 再爬所有 list 裡的 sentence
    lists = driver.find_elements(By.CSS_SELECTOR, "div.list")
    for lst in lists:
        sentences = lst.find_elements(By.CSS_SELECTOR, "div.sentence")
        for sentence in sentences:
            try:
                mp3_url = sentence.find_element(By.CSS_SELECTOR, "a.audio_1").get_attribute("href")
                ab_divs = sentence.find_elements(By.CSS_SELECTOR, "div.text > div.Ab")
                if ab_divs:
                    ab = ab_divs[-1].get_attribute("textContent").strip()
                else:
                    ab = ""
                ab_clean = clean_romaji(ab)
                ch = sentence.find_element(By.CSS_SELECTOR, "div.text > div.Ch").get_attribute("textContent").strip()
                mp3_name = f"{counter[0]:04d}.mp3"
                resp = requests.get(mp3_url)
                with open(os.path.join(audio_folder, mp3_name), "wb") as f:
                    f.write(resp.content)
                label_file.write(f"{mp3_name}\n{ch}({ab_clean})\nmale\none\n\n")
                print(f"[會話] 已爬取: {mp3_name} {ch}({ab_clean})")
                counter[0] += 1
            except Exception as e:
                print(f"[list] 解析失敗: {e}")

def go_to_word_tab(driver):
    try:
        word_tab = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'單字')]"))
        )
        word_tab.click()
        time.sleep(1.5)
    except Exception as e:
        print(f"[單字] 無法切換到單字頁: {e}")

def crawl_words(driver, audio_folder, label_file, counter):
    # 進入單字頁後，持續點擊下一個直到沒有
    while True:
        try:
            ab = driver.find_element(By.CSS_SELECTOR, "div.wrapper > div.Ab").get_attribute("textContent").strip()
            ab_clean = clean_romaji(ab)
            ch = driver.find_element(By.CSS_SELECTOR, "div.wrapper > div.Ch").get_attribute("textContent").strip()
            mp3_url = driver.find_element(By.CSS_SELECTOR, "a.audio_1").get_attribute("href")
            mp3_name = f"{counter[0]:04d}.mp3"
            resp = requests.get(mp3_url)
            with open(os.path.join(audio_folder, mp3_name), "wb") as f:
                f.write(resp.content)
            label_file.write(f"{mp3_name}\n{ch}({ab_clean})\nmale\none\n\n")
            print(f"[單字] 已爬取: {mp3_name} {ch}({ab_clean})")
            counter[0] += 1
        except Exception as e:
            print(f"[單字] 解析失敗: {e}")
        # 檢查下一個單字按鈕
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "div.next_1")
            if next_btn.get_attribute("style") and "hidden" in next_btn.get_attribute("style"):
                break
            next_btn.click()
            time.sleep(1.2)
        except Exception:
            break

def go_to_dialogue_tab(driver):
    try:
        dialogue_tab = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'會話')]"))
        )
        dialogue_tab.click()
        time.sleep(1.5)
    except Exception as e:
        print(f"[會話] 無法切換到會話頁: {e}")

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

def crawl_life_conversation(driver, main_lang, dialect, folder_name):
    """
    爬取生活會話篇（scene + list），下載音檔與中羅文字，寫入 label.txt
    """
    # 建立資料夾
    base_folder = os.path.join(main_lang, dialect, folder_name)
    audio_folder = os.path.join(base_folder, f"{folder_name}-10", "audio")
    os.makedirs(audio_folder, exist_ok=True)
    label_txt = os.path.join(base_folder, f"{folder_name}-10", "label.txt")

    # 等待頁面載入
    time.sleep(2)

    # 點擊首頁的圖片按鈕進入主題
    try:
        img_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[3]/div[4]/div[3]/div[1]/a[1]/img'))
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
            # 1. 會話頁
            crawl_scene_and_list(driver, audio_folder, label_file, counter)
            # 2. 切到單字頁
            go_to_word_tab(driver)
            crawl_words(driver, audio_folder, label_file, counter)
            # 3. 回到會話頁
            go_to_dialogue_tab(driver)
            # 4. 檢查有沒有下一大輪
            if not has_next_round(driver):
                break
            click_next_round(driver)
            round_idx += 1
    print("生活會話篇爬取完成！")
