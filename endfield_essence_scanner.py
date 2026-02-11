import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
import pytesseract
from PIL import ImageGrab, Image
import re
from pynput import keyboard
import numpy as np
import cv2
import time
import win32api
import win32con
import win32gui
import os
import sys
from concurrent.futures import ThreadPoolExecutor
import threading
import json

# DPI 설정 (윈도우 배율 대응)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    pass

# 테서랙트 경로 및 언어 설정
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ✅ 한국어 OCR 사용 (자동 폴백 기능 포함)
def check_tesseract_language():
    """Tesseract 한국어 언어팩 설치 여부 확인"""
    try:
        # 테스트 이미지로 한국어 OCR 시도
        test_img = Image.new('RGB', (100, 30), color='white')
        pytesseract.image_to_string(test_img, lang='kor', config=r'--psm 6')
        print("✅ Tesseract 한국어 언어팩 확인 완료")
        return 'kor', r'--oem 3 --psm 6'
    except Exception as e:
        error_msg = str(e)
        if 'kor' in error_msg or 'language' in error_msg.lower():
            print("⚠️ 한국어 언어팩 없음 - 영어 모드로 폴백")
            print("💡 한국어 사용 시: https://github.com/tesseract-ocr/tessdata 에서 kor.traineddata 다운로드")
            return 'eng', r'--oem 3 --psm 6'
        else:
            print(f"⚠️ Tesseract 초기화 오류: {error_msg}")
            return 'eng', r'--oem 3 --psm 6'

# 언어팩 확인 (프로그램 시작 시 1회)
TESSERACT_LANG, TESSERACT_CONFIG = check_tesseract_language()
USE_KOREAN_OCR = (TESSERACT_LANG == 'kor')

# ============================================================
# 리소스 파일 경로 처리 (exe 빌드 대응)
# ============================================================
def resource_path(relative_path):
    """PyInstaller로 빌드된 exe에서 리소스 파일 경로 찾기"""
    try:
        # PyInstaller가 생성한 임시 폴더
        base_path = sys._MEIPASS
    except Exception:
        # 일반 Python 실행 시
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# ============================================================
# JSON 파일 로드
# ============================================================
def load_json(filename):
    """JSON 파일을 읽어서 딕셔너리로 반환"""
    try:
        filepath = resource_path(filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        messagebox.showerror("파일 오류", f"{filename} 파일을 찾을 수 없습니다.")
        return None
    except json.JSONDecodeError:
        messagebox.showerror("파일 오류", f"{filename} 파일의 JSON 형식이 올바르지 않습니다.")
        return None

# 무기 데이터베이스 로드
WEAPON_DB = load_json('weapons_db.json')

# 로드 실패 시 프로그램 종료
if WEAPON_DB is None:
    print("❌ weapons_db.json 로드 실패. 프로그램을 종료합니다.")
    exit(1)

# ✅ 해상도별 프리셋 (base_width x base_height: (start_x, start_y, spacing_x, spacing_y))
RESOLUTION_PRESETS = {
    (1280, 768): (82, 97, 105, 110),
    (1920, 1080): (123, 145, 158, 165),
    (1600, 900): (102, 121, 131, 137),
    (2560, 1440): (164, 194, 210, 220),
    (1366, 768): (87, 97, 112, 110),
}

# 전역 변수
scan_region = None
first_item_pos = None
game_window_rect = None
current_scale = 1.0
lock_button_pos = None
lock_template = None 
lock_button_template = None 
grid_spacing = (105, 110)

GRID_COLS = 4
GRID_ROWS = 5

auto_scan_enabled = False
scan_state = {"current_row": 0, "current_col": 0, "total_scanned": 0, "total_locked": 0}

# ✅ 스캔 간격 고정값 (초 단위)
scan_delay_after_click = 0.55  # 아이템 클릭 후 대기 시간 (고정)
scan_delay_between_items = 0.30  # 다음 아이템으로 넘어갈 때 대기 시간 (고정)

# ✅ 잠금 상태 캐시 (사전 스캔 결과 저장)
lock_status_cache = {}

ocr_executor = ThreadPoolExecutor(max_workers=2)
ocr_cache = {}
cache_lock = threading.Lock()

# ============================================================
# 한국어 텍스트 보정 함수 (weapons_db.json 기반)
# ============================================================
def normalize_korean_text(text):
    """
    OCR로 인식된 한국어 텍스트를 정규화하여 weapons_db.json의 옵션과 매칭
    """
    import re
    
    # 1. 공백 제거 및 한글만 추출
    clean = re.sub(r'\s+', '', text)
    clean = re.sub(r'[^\uAC00-\uD7A3]', '', clean)
    
    if not clean:
        return None
    
    # 2. 접미사 제거 (증가 관련 오타 모두 처리)
    clean = re.sub(r'(증가|흐가|쿨가|흐쿨|골흐|콜흐|툴골|즘가|승가|즐|증|가|중)$', '', clean)
    
    # 공백 다시 제거
    clean = re.sub(r'\s+', '', clean)
    
    if not clean:
        return None
    
    # ⭐ 3. 긴 단어 우선 매칭 (겹침 방지)
    # "궁극기 충전 효율" - 모든 키워드가 있어야 매칭
    if (re.search(r'궁[극국귱]', clean) and 
        re.search(r'충[전젼]', clean) and 
        re.search(r'효[율률]', clean)):
        return "궁극기 충전 효율"
    
    # "주요 능력치"
    if re.search(r'주[요오]|능[력럭]', clean):
        return "주요 능력치"
    
    # "치명타 확률" → "치확" (weapons_db 표기)
    if re.search(r'치[명망]|확[률를]', clean) or re.search(r'^치확$', clean):
        return "치확"
    
    # "치유 효율" - "치유"와 "효율" 모두 있어야 매칭
    if re.search(r'치[유우]', clean) and re.search(r'효[율률]', clean):
        return "치유 효율"
    
    # 4. 핵심 스탯 오타 보정
    # "공격력"
    if re.search(r'걱럭|격턱|공[격걱]|격력|공력|^럭$|^공$|콜굴|콜골|휼콜|드룰', clean):
        return "공격력"
    
    # "생명력"
    if re.search(r'생[명멍먕]', clean):
        return "생명력"
    
    # "민첩성" (weapons_db 표기)
    if re.search(r'민[첩접쳡]', clean):
        return "민첩성"
    
    # "지능"
    if re.search(r'지[능늄]|시능|자능', clean):
        return "지능"
    
    # "의지"
    if re.search(r'의[지자]|으지|휼|외지|의치', clean):
        return "의지"
    
    # "힘"
    if re.search(r'^힘$|흐임|그[룹룰옵루]|^[으우]루$|^루$', clean):
        return "힘"
    
    # 5. 아츠 관련
    # "아츠 강도"
    if re.search(r'아[츠즈측].*강[도돠]', clean) or (re.search(r'아[츠즈측]', clean) and re.search(r'강[도돠]', clean)):
        return "아츠 강도"
    
    # "아츠 피해"
    if re.search(r'아[츠즈측].*피[해혜]', clean) or (re.search(r'아[츠즈측]', clean) and re.search(r'피[해혜]', clean)):
        return "아츠 피해"
    
    # 6. 속성 피해
    if re.search(r'물[리이]|그리', clean) and re.search(r'피[해혜]', clean):
        return "물리 피해"
    if re.search(r'냉[기기]', clean) and re.search(r'피[해혜]', clean):
        return "냉기 피해"
    if re.search(r'열[기이]', clean) and re.search(r'피[해혜]', clean):
        return "열기 피해"
    if re.search(r'전[기이]', clean) and re.search(r'피[해혜]', clean):
        return "전기 피해"
    if re.search(r'자[연현]', clean) and re.search(r'피[해혜]', clean):
        return "자연 피해"
    
    # 7. 서브 옵션 (weapons_db 기준)
    if re.search(r'방[출줄쥴]|밤출', clean):
        return "방출"
    if re.search(r'흐[름륾]|으름', clean):
        return "흐름"
    if re.search(r'고[통충동]', clean):
        return "고통"
    if re.search(r'^어[둠눔롬놈돔룸듬]$|^[어엄움]$', clean):
        return "어둠"
    if re.search(r'강[공곡골콜쿠쿨]', clean):
        return "강공"
    if re.search(r'억[제재]', clean):
        return "억제"
    if re.search(r'잔[혹흑]', clean):
        return "잔혹"
    if re.search(r'추[격굑]', clean):
        return "추격"
    if re.search(r'기[예얘]', clean):
        return "기예"
    if re.search(r'골[절졀]', clean):
        return "골절"
    if re.search(r'분[쇄쉐]', clean):
        return "분쇄"
    if re.search(r'사[기귀]', clean):
        return "사기"
    if re.search(r'의[료로]', clean):
        return "의료"
    # ⭐ "효율"은 가장 마지막에 체크 (다른 복합어 매칭 후)
    if re.search(r'효[율률]', clean):
        return "효율"
    
    # 8. 매칭 실패 시 None 반환
    print(f"   ⚠️ 매칭 실패: '{clean}' (원본: {text[:30]})")
    return None

def find_game_window():
    """게임 창을 찾아서 영역 반환"""
    global game_window_rect, current_scale
    
    def enum_windows_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and ('scanner' not in title.lower() and 'auto' not in title.lower()):
                if 'endfield' in title.lower() or '엔드필드' in title or '明日方舟' in title:
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width >= 800 and height >= 600:
                        windows.append((hwnd, title, width, height))
                        print(f"🔍 발견된 게임 창: '{title}' ({width}x{height})")
    
    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    
    print(f"📊 총 {len(windows)}개의 게임 창 발견")
    
    if not windows:
        status_label.config(text="❌ 게임 창을 찾을 수 없습니다", fg="#e74c3c")
        print("⚠️ 게임 창 검색 실패")
        return False
    
    windows.sort(key=lambda x: x[2] * x[3], reverse=True)
    hwnd, title, width, height = windows[0]
    
    print(f"✅ 선택된 창: '{title}' ({width}x{height})")
    
    rect = win32gui.GetWindowRect(hwnd)
    
    try:
        client_rect = win32gui.GetClientRect(hwnd)
        client_width = client_rect[2]
        client_height = client_rect[3]
        client_pos = win32gui.ClientToScreen(hwnd, (0, 0))
        
        game_window_rect = {
            'x': client_pos[0],
            'y': client_pos[1],
            'width': client_width,
            'height': client_height
        }
    except:
        x, y, x2, y2 = rect
        title_bar_height = 30
        border_width = 8
        
        game_window_rect = {
            'x': x + border_width,
            'y': y + title_bar_height,
            'width': width - border_width * 2,
            'height': height - title_bar_height - border_width
        }
    
    base_width = 1280
    base_height = 768
    current_scale = game_window_rect['width'] / base_width
    
    print(f"🎮 게임 창 최종 선택: {title}")
    print(f"📏 클라이언트 영역: ({game_window_rect['x']}, {game_window_rect['y']}) {game_window_rect['width']}x{game_window_rect['height']}")
    print(f"📐 스케일: {current_scale:.2f}x")
    
    return True

def get_scaled_value(base_value):
    return int(base_value * current_scale)

def click_position(pos):
    if not pos: return False
    x, y = pos
    try:
        # 1. 마우스 이동
        win32api.SetCursorPos((x, y))
        time.sleep(0.1)
        
        # 2. 클릭 다운
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        
        # 3. 클릭 업
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.05)
        
        print(f"   🖱️ 클릭 완료: ({x}, {y})")
        return True
    except Exception as e:
        print(f"   ❌ 클릭 실패: {str(e)}")
        return False

def detect_yellow_items():
    try:
        if game_window_rect:
            bbox = (
                game_window_rect['x'],
                game_window_rect['y'],
                game_window_rect['x'] + game_window_rect['width'],
                game_window_rect['y'] + game_window_rect['height']
            )
            screen = np.array(ImageGrab.grab(bbox=bbox))
            offset_x, offset_y = game_window_rect['x'], game_window_rect['y']
        else:
            screen = np.array(ImageGrab.grab())
            offset_x, offset_y = 0, 0
        
        hsv = cv2.cvtColor(screen, cv2.COLOR_RGB2HSV)
        lower_yellow = np.array([15, 150, 150])
        upper_yellow = np.array([35, 255, 255])
        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detected_points = []
        min_width = get_scaled_value(40)
        max_height = get_scaled_value(15)
        y_offset = get_scaled_value(60)
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > min_width and h < max_height:
                item_center = (offset_x + x + w//2, offset_y + y - y_offset)
                detected_points.append(item_center)
        
        return detected_points
    except: 
        return []

def is_item_at_position(target_pos, tolerance=None):
    if tolerance is None:
        tolerance = get_scaled_value(70)
    
    detected_items = detect_yellow_items()
    if not detected_items:
        return False
    for item_pos in detected_items:
        if abs(item_pos[0] - target_pos[0]) < tolerance and abs(item_pos[1] - target_pos[1]) < tolerance:
            return True
    return False

def load_lock_template():
    global lock_template, lock_button_template
    
    lock_template_path = resource_path("lock_template.png")
    lock_button_template_path = resource_path("lock_button_template.png")
    
    if os.path.exists(lock_template_path):
        lock_template = cv2.imread(lock_template_path, cv2.IMREAD_GRAYSCALE)
        print("✅ lock_template.png 로드 완료")
    else:
        print("❌ lock_template.png 없음")
        
    if os.path.exists(lock_button_template_path):
        lock_button_template = cv2.imread(lock_button_template_path, cv2.IMREAD_GRAYSCALE)
        print("✅ lock_button_template.png 로드 완료")
    else:
        print("❌ lock_button_template.png 없음")

def find_lock_button():
    global lock_button_template
    if lock_button_template is None: return None
    try:
        if game_window_rect:
            screen_width = game_window_rect['x'] + game_window_rect['width']
            screen_height = game_window_rect['y'] + game_window_rect['height']
            search_bbox = (
                game_window_rect['x'] + game_window_rect['width'] // 2,
                game_window_rect['y'],
                screen_width,
                screen_height
            )
        else:
            screen = ImageGrab.grab()
            screen_width = screen.width
            search_bbox = (screen_width // 2, 0, screen_width, screen.height)
        
        search_img = ImageGrab.grab(bbox=search_bbox)
        search_gray = cv2.cvtColor(np.array(search_img), cv2.COLOR_RGB2GRAY)
        
        if current_scale != 1.0:
            scaled_w = int(lock_button_template.shape[1] * current_scale)
            scaled_h = int(lock_button_template.shape[0] * current_scale)
            scaled_template = cv2.resize(lock_button_template, (scaled_w, scaled_h))
        else:
            scaled_template = lock_button_template
        
        result = cv2.matchTemplate(search_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val >= 0.7:
            h, w = scaled_template.shape
            return (search_bbox[0] + max_loc[0] + w // 2, search_bbox[1] + max_loc[1] + h // 2)
        return None
    except: return None

def is_item_locked_template(item_pos):
    global lock_template
    if lock_template is None:
        return False
    
    try:
        cell_half_w = int(grid_spacing[0] * 0.45)
        cell_half_h = int(grid_spacing[1] * 0.45)
        icon_offset_x = -int(grid_spacing[0] * 0.38)
        icon_offset_y = int(grid_spacing[1] * 0.25)

        icon_center_x = item_pos[0] + icon_offset_x
        icon_center_y = item_pos[1] + icon_offset_y

        search_x1 = icon_center_x - cell_half_w
        search_y1 = icon_center_y - cell_half_h
        search_x2 = icon_center_x + cell_half_w
        search_y2 = icon_center_y + cell_half_h

        search_x1 = max(0, search_x1)
        search_y1 = max(0, search_y1)
        search_bbox = (search_x1, search_y1, search_x2, search_y2)

        if (search_x2 - search_x1) < 10 or (search_y2 - search_y1) < 10:
            print(f"  ⚠️ 검색 영역 너무 작음: {search_bbox}")
            return False

        search_img = ImageGrab.grab(bbox=search_bbox)
        search_gray = cv2.cvtColor(np.array(search_img), cv2.COLOR_RGB2GRAY)

        if current_scale != 1.0:
            scaled_w = max(1, int(lock_template.shape[1] * current_scale))
            scaled_h = max(1, int(lock_template.shape[0] * current_scale))
            scaled_template = cv2.resize(lock_template, (scaled_w, scaled_h))
        else:
            scaled_template = lock_template

        if (scaled_template.shape[1] > search_gray.shape[1] or
                scaled_template.shape[0] > search_gray.shape[0]):
            print(f"  ⚠️ 템플릿({scaled_template.shape[1]}x{scaled_template.shape[0]})이 "
                  f"검색영역({search_gray.shape[1]}x{search_gray.shape[0]})보다 큼 → 잠금 안됨 처리")
            return False

        result = cv2.matchTemplate(search_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        is_locked = max_val >= 0.78
        print(f"  🔎 잠금 감지: 검색영역={search_bbox} | 매칭점수={max_val:.3f} | "
              f"임계값=0.78 | {'🔒 잠금됨' if is_locked else '🔓 잠금안됨'}")

        return is_locked

    except Exception as e:
        print(f"  ❌ 잠금 감지 오류: {str(e)}")
        return False

def auto_detect_option_region():
    global scan_region
    try:
        status_label.config(text="🔍 옵션 영역 찾는 중...", fg="#f39c12")
        root.update()
        
        if game_window_rect:
            bbox = (
                game_window_rect['x'],
                game_window_rect['y'],
                game_window_rect['x'] + game_window_rect['width'],
                game_window_rect['y'] + game_window_rect['height']
            )
            screen = np.array(ImageGrab.grab(bbox=bbox))
            offset_x, offset_y = game_window_rect['x'], game_window_rect['y']
        else:
            screen = np.array(ImageGrab.grab())
            offset_x, offset_y = 0, 0
        
        hsv = cv2.cvtColor(screen, cv2.COLOR_RGB2HSV)
        lower_yellow = np.array([20, 100, 150])
        upper_yellow = np.array([35, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        min_height = get_scaled_value(30)
        max_width = get_scaled_value(20)
        
        yellow_bars = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > w and h > min_height and w < max_width:
                yellow_bars.append((x, y, w, h))
        
        if len(yellow_bars) < 1:
            print("⚠️ 옵션 영역 자동 감지 실패 - 기본값 사용")
            scan_region = (
                game_window_rect['x'] + get_scaled_value(560),
                game_window_rect['y'] + get_scaled_value(200),
                game_window_rect['x'] + get_scaled_value(820),
                game_window_rect['y'] + get_scaled_value(450)
            )
            return
            
        yellow_bars.sort(key=lambda b: b[1])
        top_3 = yellow_bars[:3]
        
        padding = get_scaled_value(15)
        width_extend = get_scaled_value(240)
        
        min_x = offset_x + min(b[0] for b in top_3) + padding
        min_y = offset_y + min(b[1] for b in top_3)
        max_x = offset_x + max(b[0] + b[2] for b in top_3) + width_extend
        max_y = offset_y + max(b[1] + b[3] for b in top_3)
        
        scan_region = (min_x, min_y, max_x, max_y)
        print(f"✅ 옵션 영역 감지 성공: {scan_region}")
    except Exception as e:
        print(f"❌ 옵션 영역 감지 오류: {str(e)}")
        scan_region = (
            game_window_rect['x'] + get_scaled_value(560),
            game_window_rect['y'] + get_scaled_value(200),
            game_window_rect['x'] + get_scaled_value(820),
            game_window_rect['y'] + get_scaled_value(450)
        )

def auto_detect_grid():
    global first_item_pos, grid_spacing
    
    try:
        status_label.config(text="🔍 아이템 그리드 감지 중...", fg="#f39c12")
        root.update()
        
        res_key = (game_window_rect['width'], game_window_rect['height'])
        preset_found = False
        
        for preset_res, preset_vals in RESOLUTION_PRESETS.items():
            if abs(res_key[0] - preset_res[0]) < 50 and abs(res_key[1] - preset_res[1]) < 50:
                start_x, start_y, spacing_x, spacing_y = preset_vals
                first_item_pos = (game_window_rect['x'] + start_x, game_window_rect['y'] + start_y)
                grid_spacing = (spacing_x, spacing_y)
                preset_found = True
                print(f"✅ 프리셋 사용: {preset_res} -> start({start_x},{start_y}) spacing({spacing_x},{spacing_y})")
                break
        
        if not preset_found:
            base_start = (82, 97)
            base_spacing = (105, 110)
            
            first_item_pos = (
                game_window_rect['x'] + get_scaled_value(base_start[0]),
                game_window_rect['y'] + get_scaled_value(base_start[1])
            )
            grid_spacing = (
                get_scaled_value(base_spacing[0]),
                get_scaled_value(base_spacing[1])
            )
            print(f"✅ 스케일 계산: scale={current_scale:.2f}x")
        
        detected_items = detect_yellow_items()
        
        if len(detected_items) >= 4:
            left_top_items = [
                item for item in detected_items
                if item[0] < game_window_rect['x'] + game_window_rect['width'] * 0.6
                and item[1] < game_window_rect['y'] + game_window_rect['height'] * 0.4
            ]
            
            if len(left_top_items) >= 4:
                left_top_items.sort(key=lambda p: p[0] + p[1])
                detected_first = left_top_items[0]
                
                diff_x = abs(detected_first[0] - first_item_pos[0])
                diff_y = abs(detected_first[1] - first_item_pos[1])
                
                if diff_x > 20 or diff_y > 20:
                    print(f"⚠️ 계산 위치와 감지 위치 차이 큼: ({diff_x}, {diff_y})")
                    print(f"   계산: {first_item_pos} -> 감지: {detected_first}")
                    first_item_pos = detected_first
                    
                    sorted_by_x = sorted(left_top_items, key=lambda p: p[0])
                    sorted_by_y = sorted(left_top_items, key=lambda p: p[1])
                    
                    if len(sorted_by_x) >= 2:
                        x_diffs = [sorted_by_x[i+1][0] - sorted_by_x[i][0] 
                                  for i in range(min(3, len(sorted_by_x)-1))]
                        avg_x_spacing = int(np.median(x_diffs))
                        grid_spacing = (avg_x_spacing, grid_spacing[1])
                        print(f"   X 간격 재계산: {avg_x_spacing}")
                    
                    if len(sorted_by_y) >= 2:
                        y_diffs = [sorted_by_y[i+1][1] - sorted_by_y[i][1] 
                                  for i in range(min(3, len(sorted_by_y)-1))]
                        avg_y_spacing = int(np.median(y_diffs))
                        grid_spacing = (grid_spacing[0], avg_y_spacing)
                        print(f"   Y 간격 재계산: {avg_y_spacing}")
                else:
                    print(f"✅ 계산 위치 검증 완료 (오차: {diff_x}, {diff_y})")
        
        print(f"📍 최종 첫 아이템 위치: {first_item_pos}")
        print(f"📏 최종 간격: {grid_spacing}")
        status_label.config(text="⏳ 대기 중...", fg="#95a5a6")
        
    except Exception as e:
        status_label.config(text=f"❌ 오류: {str(e)}", fg="#e74c3c")
        print(f"❌ 그리드 설정 오류: {str(e)}")

def get_item_position(row, col):
    if not first_item_pos: 
        return None
    
    x = first_item_pos[0] + (col * grid_spacing[0])
    y = first_item_pos[1] + (row * grid_spacing[1])
    
    return (x, y)

def pre_scan_all_locks():
    """모든 아이템의 잠금 상태를 미리 확인"""
    global lock_status_cache
    lock_status_cache.clear()
    
    print("\n" + "="*60)
    print("🔍 전체 그리드 잠금 상태 사전 스캔 시작")
    print("="*60)
    
    status_label.config(text="🔍 잠금 상태 확인 중...", fg="#f39c12")
    root.update()
    
    total_items = 0
    locked_items = 0
    
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            item_pos = get_item_position(row, col)
            
            if not is_item_at_position(item_pos):
                print(f"⚠️ [{row},{col}] 아이템 없음 - 스캔 종료")
                lock_status_cache[(row, col)] = "empty"
                status_label.config(text=f"✅ 사전 스캔 완료 ({locked_items}/{total_items} 잠금)", fg="#2ecc71")
                return total_items, locked_items
            
            total_items += 1
            
            is_locked = is_item_locked_template(item_pos)
            lock_status_cache[(row, col)] = "locked" if is_locked else "unlocked"
            
            if is_locked:
                locked_items += 1
                print(f"🔒 [{row},{col}] 잠금됨")
            else:
                print(f"🔓 [{row},{col}] 잠금 안됨")
            
            progress_label.config(text=f"사전 확인: {total_items}/20 | 잠금: {locked_items}")
            root.update()
            
            time.sleep(0.05)
    
    status_label.config(text=f"✅ 사전 스캔 완료 ({locked_items}/{total_items} 잠금)", fg="#2ecc71")
    
    print("\n" + "="*60)
    print(f"✅ 사전 스캔 완료: 총 {total_items}개 중 {locked_items}개 잠금됨")
    print("="*60 + "\n")
    
    return total_items, locked_items

# ============================================================
# 이미지 전처리 함수 (CLAHE 방식)
# ============================================================
def preprocess_image_clahe(img):
    """
    CLAHE (Contrast Limited Adaptive Histogram Equalization)
    """
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    
    scale = 3
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(resized)
    inverted = cv2.bitwise_not(enhanced)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return Image.fromarray(binary)

def scan_options_parallel(region, position=None):
    try:
        region_key = str(region)
        with cache_lock:
            if region_key in ocr_cache:
                cache_data = ocr_cache[region_key]
                if len(cache_data) == 3:
                    cache_time, result, cached_text = cache_data
                elif len(cache_data) == 2:
                    cache_time, result = cache_data
                    cached_text = "(텍스트 정보 없음)"
                else:
                    del ocr_cache[region_key]
                    cache_time = 0
                
                if cache_time > 0 and time.time() - cache_time < 1.0:
                    print(f"📦 캐시 사용")
                    if len(cache_data) == 3:
                        print(f"📄 캐시된 텍스트: {cached_text[:100]}...")
                    if result:
                        print(f"✅ 인식: {', '.join(result)}")
                    else:
                        print(f"⚠️ 인식된 키워드 없음")
                    return result
        
        img = ImageGrab.grab(bbox=region)
        
        # 이미지 밝기 체크
        img_array = np.array(img)
        avg_brightness = np.mean(img_array)
        print(f"📊 이미지 밝기: {avg_brightness:.1f}")
        
        if avg_brightness < 10:
            print(f"⚠️ 이미지가 너무 어두움 - 옵션창이 안열렸을 가능성")
            return []
        
        found_keywords = []
        
        # 한글 OCR (CLAHE 전처리)
        print(f"🔤 한글 OCR (CLAHE 전처리)")
        
        try:
            processed_img = preprocess_image_clahe(img)
            
            # 한국어 OCR 실행
            text = pytesseract.image_to_string(
                processed_img, 
                lang=TESSERACT_LANG,
                config=TESSERACT_CONFIG
            )
            
            korean_chars = 0
            total_chars = 0
            quality_score = 0
            
            if text.strip():
                korean_chars = len(re.findall(r'[\uAC00-\uD7A3]', text))
                total_chars = len(re.sub(r'\s', '', text))
                quality_score = korean_chars / max(total_chars, 1) * 100
                
                print(f"📝 한글비율: {quality_score:.0f}% | 텍스트: {text[:50]}")
                
                # ✅ 줄 단위로 분리하여 각각 정규화
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    print(f"   📋 처리 중인 줄: '{line}'")
                    normalized = normalize_korean_text(line)
                    if normalized:
                        if normalized not in found_keywords:
                            found_keywords.append(normalized)
                            print(f"      ✅ 추가됨: '{normalized}'")
                        else:
                            print(f"      ⏭️ 이미 있음: '{normalized}'")
                
                if found_keywords:
                    print(f"   ✅ 정규화: {', '.join(found_keywords)}")
            else:
                print(f"📝 인식 실패 (빈 텍스트)")
                
        except Exception as e:
            print(f"⚠️ OCR 실패: {str(e)}")
        
        # ===== 결과 처리 =====
        if not found_keywords:
            print(f"❌ OCR 완전 실패 - 인식된 키워드 없음")
            return []
        
        # 중복 제거 (순서 유지)
        found_keywords = list(dict.fromkeys(found_keywords))
        
        print(f"✅ 최종 인식: {', '.join(found_keywords)}")
        
        # 캐시 저장
        with cache_lock:
            ocr_cache[region_key] = (time.time(), found_keywords, "")
            if len(ocr_cache) > 50:
                oldest = min(ocr_cache.items(), key=lambda x: x[1][0])
                del ocr_cache[oldest[0]]
        
        return found_keywords
    except Exception as e:
        print(f"❌ OCR 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def scan_options(position=None):
    return scan_options_parallel(scan_region, position)

def check_weapon_match(options):
    """
    인식된 한글 옵션들과 무기 DB를 비교하여 매칭되는 무기 반환
    options: ["주요능력치", "공격력", "억제"] 형태의 한글 리스트
    """
    matched_weapons = []
    
    for name, req_opts in WEAPON_DB.items():
        # _comment로 시작하는 키는 건너뛰기
        if name.startswith('_comment'):
            continue
        
        # 무기가 요구하는 모든 옵션이 인식된 옵션에 포함되어 있는지 확인
        if all(opt in options for opt in req_opts):
            matched_weapons.append(name)
            print(f"   🎯 매칭: {name} (필요: {', '.join(req_opts)})")
    
    return matched_weapons

def scan_loop():
    global auto_scan_enabled, scan_state
    if not auto_scan_enabled: return
    
    row, col = scan_state["current_row"], scan_state["current_col"]
    if row >= GRID_ROWS:
        status_label.config(text=f"✅ 완료! (총 {scan_state['total_scanned']}개)", fg="#2ecc71")
        stop_scan_ui()
        return

    item_pos = get_item_position(row, col)
    
    print(f"\n{'='*50}")
    print(f"🔍 [{row},{col}] 스캔 중 - 위치: {item_pos}")
    
    # ✅ 사전 스캔 결과 확인
    cache_status = lock_status_cache.get((row, col), None)
    
    if cache_status == "empty":
        print(f"⚠️ [{row},{col}] 빈 슬롯 (사전 확인됨) - 스캔 종료")
        status_label.config(text="✅ 스캔 종료 (빈 공간)", fg="#2ecc71")
        stop_scan_ui()
        return
    
    if cache_status == "locked":
        print(f"🔒 [{row},{col}] 이미 잠금됨 (사전 확인됨) - 건너뜀")
        match_label.config(text="🔒 이미 잠금됨", fg="#95a5a6")
        option_label.config(text="건너뜀 (잠금)", fg="#95a5a6")
        
        scan_state["total_scanned"] += 1
        scan_state["current_col"] += 1
        if scan_state["current_col"] >= GRID_COLS:
            scan_state["current_col"] = 0
            scan_state["current_row"] += 1
        
        progress_label.config(text=f"진행: {scan_state['total_scanned']}/20 | 잠금: {scan_state['total_locked']}")
        root.after(200, scan_loop)
        return
    
    # 실시간 아이템 존재 확인 (이중 체크)
    if not is_item_at_position(item_pos):
        print(f"⚠️ [{row},{col}] 아이템 없음 - 스캔 종료")
        status_label.config(text="✅ 스캔 종료 (빈 공간)", fg="#2ecc71")
        stop_scan_ui()
        return
    
    print(f"✅ 아이템 감지됨 - 클릭하여 옵션 확인")
    click_position(item_pos)
    
    time.sleep(0.2)
    
    # 클릭 후 마우스를 (0, 0)으로 이동
    try:
        win32api.SetCursorPos((0, 0))
        print(f"🖱️ 마우스를 (0, 0)으로 이동")
    except:
        pass
    
    print(f"⏱️ 클릭 후 {scan_delay_after_click:.2f}초 대기 중...")
    time.sleep(scan_delay_after_click)
    
    # ✅ OCR 재시도 로직 (최대 3회)
    detected_options = []
    max_retries = 3
    
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"🔄 OCR 재시도 {attempt}/{max_retries-1}")
            time.sleep(0.25)
            
            if attempt >= 1:
                print(f"   ↻ 아이템 재클릭")
                click_position(item_pos)
                time.sleep(0.2)
                
                try:
                    win32api.SetCursorPos((0, 0))
                    print(f"   🖱️ 마우스를 (0, 0)으로 이동")
                except:
                    pass
                
                time.sleep(scan_delay_after_click)
        
        detected_options = scan_options(position=(row, col))
        
        if detected_options:
            print(f"✅ OCR 성공 ({attempt+1}번째 시도)")
            break
        else:
            print(f"⚠️ OCR 실패 ({attempt+1}번째 시도)")
            if attempt == 0:
                continue
    
    if detected_options:
        option_text = ", ".join(detected_options)
        option_label.config(text=f"감지: {option_text}", fg="#27ae60")
        
        matches = check_weapon_match(detected_options)
        if matches:
            match_text = ", ".join(matches)
            match_label.config(text=f"✅ 일치: {match_text}", fg="#27ae60")
            print(f"🎯 매칭: {match_text}")
            
            btn_pos = find_lock_button()
            if btn_pos: 
                click_position(btn_pos)
                scan_state["total_locked"] += 1
                print(f"🔐 잠금 완료")
                time.sleep(0.15)
            else:
                print(f"⚠️ 잠금 버튼 찾기 실패 - 버튼 재탐색")
                time.sleep(0.1)
                btn_pos = find_lock_button()
                if btn_pos:
                    click_position(btn_pos)
                    scan_state["total_locked"] += 1
                    print(f"🔐 잠금 완료 (재시도)")
                else:
                    print(f"❌ 잠금 버튼 찾기 완전 실패")
        else: 
            match_label.config(text="❌ 일치 없음", fg="#95a5a6")
            print(f"❌ 무기 매칭 실패")
    else: 
        option_label.config(text=f"❌ OCR 실패 ({max_retries}회)", fg="#e74c3c")
        print(f"❌ 옵션 인식 완전 실패 ({max_retries}회 시도)")
    
    scan_state["total_scanned"] += 1
    scan_state["current_col"] += 1
    if scan_state["current_col"] >= GRID_COLS:
        scan_state["current_col"] = 0
        scan_state["current_row"] += 1
    
    progress_label.config(text=f"진행: {scan_state['total_scanned']}/20 | 잠금: {scan_state['total_locked']}")
    
    next_delay_ms = int(scan_delay_between_items * 1000)
    print(f"⏱️ 다음 아이템까지 {scan_delay_between_items:.2f}초 대기...")
    root.after(next_delay_ms, scan_loop)

def toggle_auto_scan():
    global auto_scan_enabled
    if auto_scan_enabled: 
        stop_scan_ui()
        return
    
    if lock_template is None or lock_button_template is None:
        status_label.config(text="❌ 템플릿 파일 필요!", fg="#e74c3c")
        return
    
    if not find_game_window():
        response = tk.messagebox.askyesno(
            "게임 창 찾기 실패",
            "게임 창을 찾을 수 없습니다.\n\n전체 화면 사용하시겠습니까?"
        )
        if response:
            global game_window_rect, current_scale
            screen = ImageGrab.grab()
            game_window_rect = {
                'x': 0, 'y': 0,
                'width': screen.width,
                'height': screen.height
            }
            current_scale = screen.width / 1280
        else:
            return
    
    auto_detect_option_region()
    auto_detect_grid()
    
    if scan_region and first_item_pos:
        # ✅ 사전 스캔 실행
        total, locked = pre_scan_all_locks()
        
        # 잠금 가능한 아이템이 없으면 종료
        if total == locked:
            status_label.config(text="✅ 모든 아이템이 이미 잠금됨", fg="#2ecc71")
            messagebox.showinfo("스캔 완료", f"모든 아이템({total}개)이 이미 잠금되어 있습니다.")
            return
        
        auto_scan_enabled = True
        scan_state.update({"current_row": 0, "current_col": 0, "total_scanned": 0, "total_locked": 0})
        auto_btn.config(text="⏸️ 스캔 중지 (F1/F2)", style="Running.TButton")
        
        with cache_lock:
            ocr_cache.clear()
        
        scan_loop()

def stop_scan_ui():
    global auto_scan_enabled
    auto_scan_enabled = False
    auto_btn.config(text="▶️ 자동 스캔 시작 (F1)", style="TButton")

def on_key_press(key):
    try:
        if key == keyboard.Key.f1: toggle_auto_scan()
        elif key == keyboard.Key.f2: stop_scan_ui()
    except: pass

keyboard.Listener(on_press=on_key_press).start()

# ============================================================
# UI 구성 (최소화 버전)
# ============================================================
root = tk.Tk()
root.title("Endfield Auto Scanner")
root.geometry("600x600")
root.attributes("-topmost", True)
style = ttk.Style()
style.configure("Running.TButton", foreground="#e74c3c")

f = tk.Frame(root, padx=20, pady=20, bg="#ecf0f1")
f.pack(fill="both", expand=True)

# 제목
tk.Label(f, text="엔드필드 자동 잠금", font=("Malgun Gothic", 16, "bold"), bg="#ecf0f1").pack(pady=(0, 20))

# 자동 스캔 버튼
auto_btn = ttk.Button(f, text="▶️ 자동 스캔 시작 (F1)", command=toggle_auto_scan)
auto_btn.pack(pady=10, fill="x")

# 상태 라벨
status_label = tk.Label(f, text="⏳ 대기 중...", font=("Malgun Gothic", 12, "bold"), bg="#ecf0f1", fg="#95a5a6")
status_label.pack(pady=(10, 5))

# 진행 라벨
progress_label = tk.Label(f, text="진행: 0/20 | 잠금: 0", font=("Malgun Gothic", 10), bg="#ecf0f1", fg="#7f8c8d")
progress_label.pack(pady=5)

# 실시간 결과 프레임
result_frame = tk.LabelFrame(f, text="📊 실시간 결과", bg="white", padx=15, pady=10, font=("Malgun Gothic", 10, "bold"))
result_frame.pack(fill="both", expand=True, pady=(10, 0))

option_label = tk.Label(result_frame, text="감지: -", bg="white", anchor="w", font=("Malgun Gothic", 9))
option_label.pack(fill="x", pady=3)

match_label = tk.Label(result_frame, text="매칭: -", bg="white", anchor="w", font=("Malgun Gothic", 9))
match_label.pack(fill="x", pady=3)

# 도움말 (단축키만)
help_label = tk.Label(f, text="F1: 스캔 시작/중지  |  F2: 강제 중지", 
                      bg="#ecf0f1", fg="#7f8c8d", font=("Malgun Gothic", 8))
help_label.pack(pady=(10, 0))

root.after(100, load_lock_template)
root.mainloop()