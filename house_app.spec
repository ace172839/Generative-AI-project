# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

# ================= 1. 收集資料檔案 =================
datas = []

# [核心修正] 強制複製 Metadata
# 這是解決 "PackageNotFoundError: No package metadata was found for streamlit" 的關鍵
datas += copy_metadata('streamlit')
datas += copy_metadata('google-generativeai')
datas += copy_metadata('packaging')
datas += copy_metadata('numpy')
# 注意：移除了 'regex'，因為您的環境中沒有安裝，留著會報錯。

# 收集第三方套件的靜態檔案 (前端顯示需要)
datas += collect_data_files('streamlit')
datas += collect_data_files('altair')
datas += collect_data_files('pydeck')

# 加入我們的程式碼 (讓 run.py 找得到)
datas += [
    ('app.py', '.'),
    ('agent.py', '.')
]

# ================= 2. 收集隱藏模組 =================
hiddenimports = [
    'google.generativeai',
    'pandas',
    'altair',
    'pydeck',
    'sqlite3',
    'streamlit.web.cli' 
]
hiddenimports += collect_submodules('streamlit')

# ================= 3. 打包設定 =================
a = Analysis(
    ['run.py'],          # 入口點必須是 run.py (不是 app.py)
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HouseAI',       # 產生的 exe 檔名
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,         # 設為 True 可看到黑視窗報錯，確認穩定後可改 False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)