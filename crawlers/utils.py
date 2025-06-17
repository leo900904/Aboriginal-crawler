#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
爬蟲工具函式模組。
此模組包含所有爬蟲共用的功能函式。
"""

import os
import logging
import requests
from urllib.parse import urljoin
import re

# 全域設定
BASE_DOMAIN = "web.klokah.tw"

def download_audio(audio_url, filename, audio_folder):
    """下載音檔並儲存為指定檔名。"""
    try:
        full_url = urljoin(f"https://{BASE_DOMAIN}/", audio_url)
        resp = requests.get(full_url, timeout=10)
        if resp.status_code == 200:
            audio_path = os.path.join(audio_folder, filename)
            with open(audio_path, "wb") as f:
                f.write(resp.content)
            logging.info("成功下載音檔：%s" % filename)
        else:
            logging.warning("下載音檔失敗，狀態碼：%s, URL: %s", resp.status_code, audio_url)
    except Exception as e:
        logging.error("下載音檔時出錯：%s, URL: %s", e, audio_url)

def clean_romaji(romaji):
    return re.sub(r'\([^\)]*\)', '', romaji).strip()

def save_label(word_text, mp3_name, label_file):
    """將單字文字和音檔名稱儲存到標籤檔案中。"""
    if not word_text:
        return
    # 處理羅馬拼音括號
    if '(' in word_text and word_text.endswith(')'):
        # 例如: 中文(羅馬拼音)
        idx = word_text.rfind('(')
        chinese = word_text[:idx]
        romaji = word_text[idx+1:-1]
        romaji_clean = clean_romaji(romaji)
        word_text = f"{chinese}({romaji_clean})"
    try:
        with open(label_file, "a", encoding="utf-8") as f:
            f.write(mp3_name + "\n")
            f.write(word_text + "\n")
            f.write("male\n")
            f.write("one\n")
            f.write("\n")
    except Exception as e:
        logging.error("寫入 label.txt 時出錯：%s" % e)

def extract_romaji(text):
    """從文字中提取羅馬拼音。"""
    match = re.search(r'\(([^()]+)\)', text)
    if match:
        return f'({match.group(1).strip()})'
    return None 