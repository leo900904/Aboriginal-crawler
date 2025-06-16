import os
import sys
import subprocess
import platform
import glob
import re
from datetime import datetime

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

def run_cmd(cmd):
    try:
        encoding = 'utf-8' if platform.system() != "Windows" else 'cp1252'
        return subprocess.check_output(cmd, shell=True, encoding=encoding, errors='ignore').strip()
    except Exception as e:
        return f"Error: {e}"

def write_section(f, title, content):
    f.write(f"\n{'='*10} {title} {'='*10}\n")
    f.write(content + "\n")

def get_env_info():
    if 'CONDA_DEFAULT_ENV' in os.environ:
        return "Conda", os.environ.get('CONDA_DEFAULT_ENV', 'base')
    elif 'VIRTUAL_ENV' in os.environ:
        return "venv", os.path.basename(os.environ['VIRTUAL_ENV'])
    else:
        return "system", "System Python"

def get_python_version():
    return sys.version.split()[0]

def find_cudnn_header():
    cudnn_h_paths = []
    if platform.system() == "Linux":
        cudnn_h_paths = glob.glob("/usr/local/**/cudnn.h", recursive=True)
        if not cudnn_h_paths:
            cudnn_h_paths = glob.glob("/usr/include/**/cudnn.h", recursive=True)
    elif platform.system() == "Windows":
        cuda_base_paths = [
            f"C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v{version}\\include\\cudnn.h"
            for version in ["10.0", "10.1", "10.2", "11.0", "11.1", "11.2", "11.3", "11.4", "11.5", "11.6", "11.7", "11.8", "12.0", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6"]
        ]
        cudnn_h_paths = [path for path in cuda_base_paths if os.path.exists(path)]
    else:  # macOS
        cudnn_h_paths = glob.glob("/usr/local/**/cudnn.h", recursive=True)
    return cudnn_h_paths

def get_cudnn_version():
    # 如果 torch 可用，先嘗試使用 torch 獲取版本
    if TORCH_AVAILABLE:
        try:
            if torch.backends.cudnn.enabled:
                version = torch.backends.cudnn.version()
                return f"cuDNN Version: {version}"
            else:
                return "cuDNN is not enabled"
        except Exception as e:
            pass
    
    # 如果 torch 不可用或出現異常，嘗試從 cudnn.h 文件中讀取版本
    cudnn_h_paths = find_cudnn_header()
    for cudnn_h in cudnn_h_paths:
        try:
            with open(cudnn_h, encoding="utf-8", errors="ignore") as ch:
                content = ch.read()
                major = re.search(r"#define CUDNN_MAJOR\s+(\d+)", content)
                minor = re.search(r"#define CUDNN_MINOR\s+(\d+)", content)
                patch = re.search(r"#define CUDNN_PATCHLEVEL\s+(\d+)", content)
                if major and minor and patch:
                    return f"cuDNN Version: {major.group(1)}.{minor.group(1)}.{patch.group(1)}"
        except Exception:
            continue
    return "未偵測到 cudnn.h 或無法解析版本"

def get_cuda_version():
    # 如果 torch 可用，先嘗試使用 torch 獲取版本
    if TORCH_AVAILABLE:
        try:
            if torch.cuda.is_available():
                return f"CUDA Version: {torch.version.cuda}"
        except:
            pass
    
    cuda_version = run_cmd("nvcc --version")
    if "not found" not in cuda_version and "Error" not in cuda_version:
        match = re.search(r"release (\d+\.\d+)", cuda_version)
        if match:
            return f"CUDA Version: {match.group(1)}"
    
    nvidia_smi = run_cmd("nvidia-smi")
    if "not found" not in nvidia_smi and "Error" not in nvidia_smi:
        match = re.search(r"CUDA Version: (\d+\.\d+)", nvidia_smi)
        if match:
            return f"CUDA Version: {match.group(1)}"
    
    return "未偵測到 CUDA"

def get_cpu_info():
    if platform.system() == "Linux":
        return run_cmd("lscpu")
    elif platform.system() == "Windows":
        cpu_model = run_cmd("wmic cpu get name")
        cpu_cores = run_cmd("wmic cpu get numberofcores")
        cpu_threads = run_cmd("wmic cpu get numberoflogicalprocessors")
        return f"CPU 型號:\n{cpu_model}\n核心數:\n{cpu_cores}\n邏輯處理器數:\n{cpu_threads}"
    else:  # macOS
        return run_cmd("sysctl -n machdep.cpu.brand_string")

def main():
    with open("env_info.txt", "w", encoding="utf-8") as f:
        f.write(f"環境資訊記錄時間: {datetime.now()}\n")

        env_type, env_name = get_env_info()
        write_section(f, "Python 環境", f"類型: {env_type}\n名稱: {env_name}")
        write_section(f, "Python 版本", sys.version)
        write_section(f, "作業系統", platform.platform())
        write_section(f, "CPU 資訊", get_cpu_info())
        write_section(f, "pip freeze", run_cmd("pip freeze"))

        env_type, env_name = get_env_info()
        if env_type == "Conda":
            conda_env = run_cmd("conda env export --no-builds")
            if not conda_env.startswith("Error"):
                write_section(f, "conda env export", conda_env)
                env_lines = conda_env.split('\n')
                modified_env = []
                python_found = False
                python_version = get_python_version()
                
                for line in env_lines:
                    if line.startswith('prefix:'):
                        continue
                    elif line.startswith('dependencies:'):
                        modified_env.append(line)
                        modified_env.append(f"  - python={python_version}")
                        python_found = True
                    elif line.startswith('  - python=') and python_found:
                        continue
                    else:
                        modified_env.append(line)
                
                with open("environment.yml", "w", encoding="utf-8") as cf:
                    cf.write('\n'.join(modified_env) + '\n')
            else:
                write_section(f, "conda env export", "未偵測到 conda 環境")
        else:
            with open("requirements.txt", "w", encoding="utf-8") as rf:
                rf.write(run_cmd("pip freeze") + '\n')
            write_section(f, "環境匯出", f"非 Conda 環境 ({env_type})，已生成 requirements.txt")

        write_section(f, "CUDA 版本", get_cuda_version())
        write_section(f, "cuDNN 版本", get_cudnn_version())
        write_section(f, "NVIDIA 驅動與顯卡", run_cmd("nvidia-smi"))

    print("環境資訊已寫入以下檔案：")
    print("1. env_info.txt - 完整環境資訊")
    if env_type == "Conda":
        print("2. environment.yml - 完整 conda 環境設定（已移除系統特定路徑並指定 Python 版本）")
    else:
        print("2. requirements.txt - pip 套件清單")
    print("\n重建環境的方法：")
    if env_type == "Conda":
        print("conda env create -f environment.yml")
    elif env_type == "venv":
        print("python -m venv env_name && pip install -r requirements.txt")
    else:
        print("pip install -r requirements.txt")

if __name__ == "__main__":
    main()