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

# 테서랙트 경로 (본인의 설치 경로에 맞게 확인 필요)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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

# 데이터베이스 로드
TARGET_KEYWORDS = load_json('attributes_db.json')
WEAPON_DB = load_json('weapons_db.json')

# 로드 실패 시 프로그램 종료
if TARGET_KEYWORDS is None or WEAPON_DB is None:
    print("❌ 데이터베이스 파일 로드 실패. 프로그램을 종료합니다.")
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
        game_window_label.config(text="❌ 게임 창을 찾을 수 없습니다", fg="#e74c3c")
        status_label.config(text="💡 게임을 먼저 실행하세요", fg="#f39c12")
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
    
    game_window_label.config(
        text=f"✅ '{title[:30]}...' {game_window_rect['width']}x{game_window_rect['height']} (스케일: {current_scale:.2f}x)",
        fg="#27ae60"
    )
    
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
        win32api.SetCursorPos((x, y))
        time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        return True
    except: return False

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
    if os.path.exists(lock_button_template_path):
        lock_button_template = cv2.imread(lock_button_template_path, cv2.IMREAD_GRAYSCALE)
    
    if lock_template is not None:
        template_label.config(text="✅ 아이콘 템플릿 로드 완료", fg="#27ae60")
    else:
        template_label.config(text="❌ lock_template.png 없음", fg="#e74c3c")
    if lock_button_template is not None:
        lock_btn_label.config(text="✅ 버튼 템플릿 로드 완료", fg="#27ae60")
    else:
        lock_btn_label.config(text="❌ lock_button_template.png 없음", fg="#e74c3c")

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
            print("⚠️ 옵션 영역 자동 감지 실패 - 수동 설정 필요")
            # 기본값 설정 (1280x768 기준)
            scan_region = (
                game_window_rect['x'] + get_scaled_value(560),
                game_window_rect['y'] + get_scaled_value(200),
                game_window_rect['x'] + get_scaled_value(820),
                game_window_rect['y'] + get_scaled_value(450)
            )
            scan_region_label.config(text=f"⚠️ 기본값 사용: {scan_region}", fg="#f39c12")
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
        scan_region_label.config(text=f"✅ 옵션 영역: ({min_x},{min_y}) ~ ({max_x},{max_y})", fg="#27ae60")
        print(f"✅ 옵션 영역 감지 성공: {scan_region}")
    except Exception as e:
        print(f"❌ 옵션 영역 감지 오류: {str(e)}")
        # 오류 시 기본값
        scan_region = (
            game_window_rect['x'] + get_scaled_value(560),
            game_window_rect['y'] + get_scaled_value(200),
            game_window_rect['x'] + get_scaled_value(820),
            game_window_rect['y'] + get_scaled_value(450)
        )
        scan_region_label.config(text=f"⚠️ 기본값 사용 (오류)", fg="#e74c3c")

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
        
        rel_x = first_item_pos[0] - game_window_rect['x']
        rel_y = first_item_pos[1] - game_window_rect['y']
        
        auto_setup_label.config(
            text=f"✅ 기준점: 창내({rel_x},{rel_y}) / 화면{first_item_pos}",
            fg="#27ae60"
        )
        spacing_label.config(
            text=f"✅ 간격: 가로 {grid_spacing[0]}px, 세로 {grid_spacing[1]}px",
            fg="#27ae60"
        )
        status_label.config(text="👍 그리드 설정 완료!", fg="#2ecc71")
        
        print(f"📍 최종 첫 아이템 위치: {first_item_pos} (상대: {rel_x}, {rel_y})")
        print(f"📏 최종 간격: {grid_spacing}")
        
    except Exception as e:
        status_label.config(text=f"❌ 오류: {str(e)}", fg="#e74c3c")
        print(f"❌ 그리드 설정 오류: {str(e)}")

def get_item_position(row, col):
    if not first_item_pos: 
        return None
    
    x = first_item_pos[0] + (col * grid_spacing[0])
    y = first_item_pos[1] + (row * grid_spacing[1])
    
    return (x, y)

# ✅ 새로운 함수: 전체 그리드 잠금 상태 사전 스캔
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
            
            # 아이템 존재 여부 확인
            if not is_item_at_position(item_pos):
                print(f"⚠️ [{row},{col}] 아이템 없음 - 스캔 종료")
                lock_status_cache[(row, col)] = "empty"
                # 빈 슬롯 발견 시 스캔 종료
                status_label.config(text=f"✅ 사전 스캔 완료 ({locked_items}/{total_items} 잠금됨)", fg="#2ecc71")
                precheck_label.config(
                    text=f"✅ 사전 확인: {total_items}개 중 {locked_items}개 잠금됨",
                    fg="#27ae60"
                )
                return total_items, locked_items
            
            total_items += 1
            
            # 잠금 상태 확인
            is_locked = is_item_locked_template(item_pos)
            lock_status_cache[(row, col)] = "locked" if is_locked else "unlocked"
            
            if is_locked:
                locked_items += 1
                print(f"🔒 [{row},{col}] 잠금됨")
            else:
                print(f"🔓 [{row},{col}] 잠금 안됨")
            
            # UI 업데이트
            progress_label.config(
                text=f"사전 확인: {total_items}/20 | 잠금: {locked_items}"
            )
            root.update()
            
            # 약간의 딜레이 (안정성)
            time.sleep(0.05)
    
    status_label.config(text=f"✅ 사전 스캔 완료 ({locked_items}/{total_items} 잠금됨)", fg="#2ecc71")
    precheck_label.config(
        text=f"✅ 사전 확인: {total_items}개 중 {locked_items}개 잠금됨",
        fg="#27ae60"
    )
    
    print("\n" + "="*60)
    print(f"✅ 사전 스캔 완료: 총 {total_items}개 중 {locked_items}개 잠금됨")
    print("="*60 + "\n")
    
    return total_items, locked_items

def preprocess_image_method1(img):
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    scale = 2 if current_scale < 1.5 else 3
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    inverted = cv2.bitwise_not(resized)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binary)

def preprocess_image_method2(img):
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    scale = 2 if current_scale < 1.5 else 3
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    inverted = cv2.bitwise_not(resized)
    binary = cv2.adaptiveThreshold(inverted, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    return Image.fromarray(binary)

def preprocess_image_method3(img):
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    scale = 3
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(resized)
    inverted = cv2.bitwise_not(enhanced)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return Image.fromarray(binary)

def scan_options_parallel(region):
    try:
        region_key = str(region)
        with cache_lock:
            if region_key in ocr_cache:
                cache_data = ocr_cache[region_key]
                # 캐시 데이터 구조 체크 (이전 버전 호환)
                if len(cache_data) == 3:
                    cache_time, result, cached_text = cache_data
                elif len(cache_data) == 2:
                    # 이전 버전 캐시 - 텍스트 정보 없음
                    cache_time, result = cache_data
                    cached_text = "(텍스트 정보 없음)"
                else:
                    # 잘못된 캐시 - 무시
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
        
        # 이미지가 너무 어둡거나 비어있는지 체크
        img_array = np.array(img)
        avg_brightness = np.mean(img_array)
        print(f"📊 이미지 밝기: {avg_brightness:.1f} (정상: 50-200)")
        
        if avg_brightness < 10:
            print(f"⚠️ 이미지가 너무 어두움 - 옵션창이 안열렸을 가능성")
            return []
        
        preprocessing_methods = [
            preprocess_image_method1,
            preprocess_image_method2,
            preprocess_image_method3
        ]
        
        all_results = []
        
        for idx, preprocess_func in enumerate(preprocessing_methods):
            try:
                processed_img = preprocess_func(img)
                
                text = pytesseract.image_to_string(
                    processed_img, 
                    lang="eng", 
                    config=r'--oem 3 --psm 6'
                )
                
                clean_text = re.sub(r'[^a-zA-Z\s]', ' ', text).lower()
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                if clean_text:
                    all_results.append(clean_text)
                    if idx == 0:
                        print(f"📝 OCR (방법{idx+1}): {clean_text[:80]}")
                    else:
                        print(f"📝 OCR (방법{idx+1}): {clean_text[:50]}...")
                
                if len(clean_text) > 20:
                    break
                    
            except Exception as e:
                print(f"⚠️ 전처리 방법 {idx+1} 실패: {str(e)}")
                continue
        
        combined_text = ' '.join(all_results)
        
        if not combined_text:
            print(f"❌ OCR 완전 실패 - 모든 전처리 방법에서 텍스트 추출 안됨")
            return []
        
        print(f"📄 통합 텍스트: {combined_text[:100]}...")
        
        typo_fixes = {
            'atlribute': 'attribute', 'altribute': 'attribute', 
            'atribute': 'attribute', 'criticai': 'critical', 
            'rale': 'rate', 'intensily': 'intensity',
            'dmq': 'dmg', 'heai': 'heat'
        }
        for typo, correct in typo_fixes.items(): 
            combined_text = combined_text.replace(typo, correct)
        
        found_kor = []
        found_raw = []
        sorted_keys = sorted(TARGET_KEYWORDS.keys(), key=len, reverse=True)
        
        for eng in sorted_keys:
            if eng in found_raw: continue
            if ' ' in eng:
                if eng in combined_text:
                    found_kor.append(TARGET_KEYWORDS[eng])
                    found_raw.append(eng)
            else:
                if re.search(r'\b' + re.escape(eng) + r'\b', combined_text):
                    found_kor.append(TARGET_KEYWORDS[eng])
                    found_raw.append(eng)
        
        if found_raw:
            print(f"✅ 인식: {', '.join(found_raw)}")
        else:
            print(f"⚠️ 키워드 매칭 실패 (원본: {combined_text[:50]}...)")
        
        with cache_lock:
            ocr_cache[region_key] = (time.time(), found_kor, combined_text)
            if len(ocr_cache) > 50:
                oldest = min(ocr_cache.items(), key=lambda x: x[1][0])
                del ocr_cache[oldest[0]]
        
        return found_kor
    except Exception as e:
        print(f"❌ OCR 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def scan_options():
    return scan_options_parallel(scan_region)

def check_weapon_match(options):
    return [name for name, req in WEAPON_DB.items() if all(opt in options for opt in req)]

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
    
    # ✅ 사용자 설정 대기 시간 적용
    delay_ms = int(scan_delay_after_click * 1000)
    print(f"⏱️ 클릭 후 {scan_delay_after_click:.2f}초 대기 중...")
    time.sleep(scan_delay_after_click)
    
    # ✅ OCR 재시도 로직 강화 (최대 3회)
    detected_options = []
    max_retries = 3
    
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"🔄 OCR 재시도 {attempt}/{max_retries-1}")
            time.sleep(0.25)  # 재시도 전 대기
            
            # 재시도 시 다시 클릭 (옵션창이 안열렸을 수 있음)
            if attempt == 2:
                print(f"   ↻ 아이템 재클릭")
                click_position(item_pos)
                time.sleep(scan_delay_after_click)
        
        detected_options = scan_options()
        
        if detected_options:
            print(f"✅ OCR 성공 ({attempt+1}번째 시도)")
            break
        else:
            print(f"⚠️ OCR 실패 ({attempt+1}번째 시도)")
    
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
    
    # ✅ 사용자 설정 대기 시간 적용
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
            game_window_label.config(
                text=f"✅ 전체 화면: {screen.width}x{screen.height} ({current_scale:.2f}x)",
                fg="#f39c12"
            )
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

root = tk.Tk()
root.title("Endfield Auto Scanner v7.3 (Fixed Delay)")
root.geometry("540x980")
root.attributes("-topmost", True)
style = ttk.Style()
style.configure("Running.TButton", foreground="#e74c3c")

f = tk.Frame(root, padx=20, pady=20, bg="#ecf0f1")
f.pack(fill="both", expand=True)

tk.Label(f, text="엔드필드 자동 잠금 (간격 고정)", font=("Malgun Gothic", 16, "bold"), bg="#ecf0f1").pack(pady=10)

setup_frame = tk.LabelFrame(f, text="📊 상태", bg="white", padx=10, pady=10)
setup_frame.pack(fill="x", pady=10)
game_window_label = tk.Label(setup_frame, text="게임 창: 대기", bg="white", fg="#95a5a6")
game_window_label.pack(anchor="w")
template_label = tk.Label(setup_frame, text="템플릿 로딩 중...", bg="white", fg="#95a5a6")
template_label.pack(anchor="w")
lock_btn_label = tk.Label(setup_frame, text="버튼 템플릿 로딩 중...", bg="white", fg="#95a5a6")
lock_btn_label.pack(anchor="w")
scan_region_label = tk.Label(setup_frame, text="옵션 영역: 대기", bg="white", fg="#95a5a6")
scan_region_label.pack(anchor="w")
auto_setup_label = tk.Label(setup_frame, text="그리드: 대기", bg="white", fg="#95a5a6")
auto_setup_label.pack(anchor="w")
spacing_label = tk.Label(setup_frame, text="간격: 대기", bg="white", fg="#95a5a6")
spacing_label.pack(anchor="w")
precheck_label = tk.Label(setup_frame, text="사전 확인: 대기", bg="white", fg="#95a5a6")
precheck_label.pack(anchor="w")

# ✅ 스캔 간격 표시 (고정값)
delay_frame = tk.LabelFrame(f, text="⏱️ 스캔 간격 (고정)", bg="white", padx=10, pady=10)
delay_frame.pack(fill="x", pady=10)

tk.Label(
    delay_frame, 
    text=f"• 아이템 클릭 후 대기: {scan_delay_after_click:.2f}초", 
    bg="white", 
    anchor="w",
    font=("Malgun Gothic", 9)
).pack(anchor="w", pady=2)

tk.Label(
    delay_frame, 
    text=f"• 다음 아이템 대기: {scan_delay_between_items:.2f}초", 
    bg="white", 
    anchor="w",
    font=("Malgun Gothic", 9)
).pack(anchor="w", pady=2)

auto_btn = ttk.Button(f, text="▶️ 자동 스캔 시작 (F1)", command=toggle_auto_scan)
auto_btn.pack(pady=10, fill="x")

status_label = tk.Label(f, text="⏳ 대기 중...", font=("Malgun Gothic", 12, "bold"), bg="#ecf0f1")
status_label.pack()
progress_label = tk.Label(f, text="진행: 0/20 | 잠금: 0", bg="#ecf0f1")
progress_label.pack()

result_frame = tk.LabelFrame(f, text="📊 실시간 결과", bg="white", padx=10, pady=10)
result_frame.pack(fill="both", expand=True, pady=10)
option_label = tk.Label(result_frame, text="감지: -", bg="white", anchor="w")
option_label.pack(fill="x")
match_label = tk.Label(result_frame, text="매칭: -", bg="white", anchor="w")
match_label.pack(fill="x")

help_frame = tk.LabelFrame(f, text="💡 도움말", bg="white", padx=10, pady=5)
help_frame.pack(fill="x", pady=5)
tk.Label(help_frame, text="• 시작 전 모든 아이템의 잠금 상태 확인", bg="white", anchor="w", font=("Malgun Gothic", 8)).pack(anchor="w")
tk.Label(help_frame, text="• 클릭 후 0.55초, 다음 아이템 0.30초 대기", bg="white", anchor="w", font=("Malgun Gothic", 8)).pack(anchor="w")
tk.Label(help_frame, text="• F1: 스캔 시작/중지, F2: 강제 중지", bg="white", anchor="w", font=("Malgun Gothic", 8)).pack(anchor="w")

root.after(100, load_lock_template)
root.mainloop()
