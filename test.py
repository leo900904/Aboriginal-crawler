import os
import shutil
from pathlib import Path

def find_target_folders(root_dir: Path):
    """尋找所有以 '-10' 結尾的資料夾"""
    target_folders = []
    for folder in root_dir.rglob('*-10'):
        if folder.is_dir():
            target_folders.append(folder)
    return target_folders

def copy_folder_structure(src_folder: Path, dest_folder: Path, record_num: int):
    """複製資料夾結構並重新命名"""
    new_folder_name = f"record{record_num}-10"
    dest_path = dest_folder / new_folder_name

    if dest_path.exists():
        shutil.rmtree(dest_path)

    shutil.copytree(src_folder, dest_path)
    print(f"已複製 {src_folder} 到 {dest_path}")
    return new_folder_name

def save_mapping_file(output_dir: Path, mappings: list):
    """保存資料夾對照表"""
    mapping_file = output_dir / "folder_mapping.txt"
    with open(mapping_file, 'w', encoding='utf-8') as f:
        f.write("=== 資料夾對照表 ===\n")
        f.write("原始資料夾 -> 新資料夾\n")
        f.write("=" * 50 + "\n")
        for original, new in mappings:
            f.write(f"{original} -> {new}\n")
    print(f"\n對照表已保存至: {mapping_file}")

def main():
    # 取得此腳本檔所在目錄
    base_dir = Path(__file__).resolve().parent

    # 改成相對路徑：假設來源資料夾在腳本同級的 "阿美語"，輸出到同級的 "整理後資料"
    source_dir = base_dir / "排灣語"
    output_dir = base_dir / "排灣語2025-06-12"

    # 確保輸出目錄存在
    output_dir.mkdir(exist_ok=True)

    # 尋找所有目標資料夾
    target_folders = find_target_folders(source_dir)

    if not target_folders:
        print("未找到任何包含 '-10' 的資料夾")
        return

    print(f"\n找到 {len(target_folders)} 個目標資料夾:")
    for i, folder in enumerate(target_folders, 1):
        print(f"{i}. {folder}")

    confirm = input("\n是否要開始複製這些資料夾？(y/n): ").strip().lower()
    if confirm != 'y':
        print("操作已取消")
        return

    # 記錄對照關係
    folder_mappings = []
    for i, folder in enumerate(target_folders, 1):
        new_name = copy_folder_structure(folder, output_dir, i)
        folder_mappings.append((folder.name, new_name))

    # 保存對照表
    save_mapping_file(output_dir, folder_mappings)

    print(f"\n完成！共處理了 {len(target_folders)} 個資料夾")
    print(f"輸出目錄: {output_dir}")

if __name__ == "__main__":
    main()
