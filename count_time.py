from pathlib import Path
from pydub import AudioSegment
import time
from datetime import timedelta

def format_time(seconds):
    """將秒數轉換為時:分:秒格式"""
    return str(timedelta(seconds=int(seconds)))

def get_audio_duration(file_path):
    """獲取音檔時長（秒）"""
    try:
        audio = AudioSegment.from_file(file_path)
        duration = len(audio) / 1000.0  # 轉換為秒
        return duration, False, ""  # 成功時返回：時長, 非損壞, 無錯誤訊息
    except Exception as e:
        error_msg = str(e)
        if "Failed to find two consecutive MPEG audio frames" in error_msg:
            print(f"警告：檔案 {file_path} 可能是損壞的MP3檔案")
            return 0, True, "損壞的MP3檔案"
        elif "Invalid data found when processing input" in error_msg:
            print(f"警告：檔案 {file_path} 包含無效的音訊資料")
            return 0, True, "無效的音訊資料"
        else:
            print(f"無法讀取檔案 {file_path}: {error_msg}")
            return 0, True, error_msg

def count_audio_files(directory: Path):
    """計算目錄中所有音檔的數量和總時長"""
    total_files = 0
    total_duration = 0
    folder_stats = {}
    broken_files = []

    # 支援的音檔格式
    audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}

    # 遞迴遍歷所有音檔
    print(f"開始遞迴搜尋目錄: {directory}")
    for file in directory.rglob('*'):
        if file.is_file() and file.suffix.lower() in audio_extensions:
            print(f"處理檔案: {file}")
            duration, is_broken, error_msg = get_audio_duration(file)
            total_files += 1
            total_duration += duration
            
            if is_broken:
                broken_files.append({
                    'path': str(file),
                    'error': error_msg
                })
            
            # 統計每個資料夾的檔案數量和時長
            parent_folder = str(file.parent)
            if parent_folder not in folder_stats:
                folder_stats[parent_folder] = {
                    'files': 0,
                    'duration': 0
                }
            folder_stats[parent_folder]['files'] += 1
            folder_stats[parent_folder]['duration'] += duration

    return total_files, total_duration, folder_stats, broken_files

def save_broken_files(directory: Path, broken_files: list):
    """保存損壞檔案列表"""
    broken_file = directory / "broken.txt"
    with open(broken_file, 'w', encoding='utf-8') as f:
        f.write("=== 損壞的音檔列表 ===\n")
        f.write("檔案路徑 -> 錯誤訊息\n")
        f.write("=" * 50 + "\n")
        for file_info in broken_files:
            f.write(f"{file_info['path']} -> {file_info['error']}\n")
    print(f"\n損壞檔案列表已保存至: {broken_file}")

def main():
    # 取得此腳本檔所在目錄
    base_dir = Path(__file__).resolve().parent
    
    # 設定要計算的目錄（這裡使用整理後的資料目錄）
    target_dir = base_dir / "阿美語"
    
    if not target_dir.exists():
        print(f"錯誤：目錄 {target_dir} 不存在！")
        return

    print(f"開始計算 {target_dir} 中的音檔...")
    start_time = time.time()
    
    total_files, total_duration, folder_stats, broken_files = count_audio_files(target_dir)
    
    # 準備輸出結果
    output_lines = []
    output_lines.append("=== 統計結果 ===")
    output_lines.append(f"總音檔數量: {total_files}")
    output_lines.append(f"總時長: {format_time(total_duration)}")
    output_lines.append("\n各資料夾統計:")
    
    # 按資料夾名稱排序輸出
    for folder, stats in sorted(folder_stats.items()):
        output_lines.append(f"\n{folder}:")
        output_lines.append(f"  音檔數量: {stats['files']}")
        output_lines.append(f"  總時長: {format_time(stats['duration'])}")
    
    # 輸出到控制台
    print("\n".join(output_lines))
    
    # 寫入檔案
    output_file = target_dir / "total_time.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))
    
    # 保存損壞檔案列表
    if broken_files:
        save_broken_files(target_dir, broken_files)
    
    end_time = time.time()
    print(f"\n計算完成！耗時: {end_time - start_time:.2f} 秒")
    print(f"結果已寫入: {output_file}")

if __name__ == "__main__":
    main()
