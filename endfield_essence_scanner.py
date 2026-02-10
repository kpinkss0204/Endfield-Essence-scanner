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
from concurrent.futures import ThreadPoolExecutor
import threading

# DPI 설정 (윈도우 배율 대응)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    pass

# 테서랙트 경로 (본인의 설치 경로에 맞게 확인 필요)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TARGET_KEYWORDS = {
    "main attribute": "주요 능력치", "agility": "민첩성", "strength": "힘", "will": "의지", "intellect": "지능",
    "attack": "공격력", "hp": "생명력", "treatment efficiency": "치유 효율", "critical rate": "치확",
    "ultimate": "궁충", "arts intensity": "아츠 강도", "arts dmg": "아츠 피해",
    "physical": "물리 피해", "electric": "전기 피해", "heat": "열기 피해", "cryo": "냉기 피해", "nature": "자연 피해",
    "assault": "강공", "suppression": "억제", "pursuit": "추격", "crusher": "분쇄", "combative": "기예",
    "detonate": "방출", "flow": "흐름", "efficacy": "효율", "infliction": "고통", "fracture": "골절",
    "inspiring": "사기", "twilight": "어둠", "medicant": "의료", "brutality": "잔혹"
}

WEAPON_DB = {
    "백야의 별★": ["주요 능력치", "아츠 강도", "고통"],
    "위대한 이름★": ["주요 능력치", "물리 피해", "잔혹"],
    "테르밋 커터★": ["의지", "공격력", "흐름"],
    "부요★": ["주요 능력치", "치확", "어둠"],
    "끝없는 방랑★": ["의지", "공격력", "흐름"],
    "장대한 염원★": ["민첩성", "공격력", "고통"],
    "용조의 불꽃★": ["지능", "공격력", "어둠"],
    "암흑의 횃불★": ["지능", "열기 피해", "고통"],
    "강철의 여운": ["민첩성", "물리 피해", "기예"],
    "숭배의 시선": ["민첩성", "물리 피해", "어둠"],
    "O.B.J. 엣지 오브 라이트": ["민첩성", "공격력", "흐름"],
    "십이문": ["민첩성", "공격력", "고통"],
    "린수를 찾아서 3.0": ["힘", "궁충", "억제"],
    "불사의 성주": ["지능", "궁충", "사기"],
    "분쇄의 군주★": ["힘", "치확", "분쇄"],
    "과거의 일품★": ["의지", "생명력", "효율"],
    "모범★": ["주요 능력치", "공격력", "억제"],
    "헤라펜거★": ["힘", "공격력", "방출"],
    "천둥의 흔적★": ["힘", "생명력", "의료"],
    "O.B.J. 헤비 버든": ["힘", "생명력", "효율"],
    "최후의 메아리": ["힘", "생명력", "의료"],
    "고대의 강줄기": ["힘", "아츠 강도", "잔혹"],
    "검은 추적자": ["힘", "궁충", "방출"],
    "J.E.T.★": ["주요 능력치", "공격력", "억제"],
    "용사★": ["민첩성", "물리 피해", "기예"],
    "산의 지배자★": ["민첩성", "물리 피해", "효율"],
    "중심력 ": ["의지", "전기 피해", "억제"],
    "O.B.J. 스파이크": ["의지", "물리 피해", "고통"],
    "키메라의 정의": ["힘", "궁충", "잔혹"],
    "클래니벌★": ["주요 능력치", "아츠 피해", "고통"],
    "쐐기★": ["주요 능력치", "치확", "고통"],
    "예술의 폭군★": ["지능", "치확", "골절"],
    "항로의 개척자★": ["지능", "냉기 피해", "고통"],
    "이성적인 작별": ["힘", "열기 피해", "추격"],
    "O.B.J. 벨로시투스": ["민첩성", "궁충", "방출"],
    "작품: 중생": ["민첩성", "아츠 피해", "고통"],
    "기사도 정신★": ["의지", "생명력", "의료"],
    "망각★": ["지능", "아츠 피해", "어둠"],
    "폭발 유닛★": ["주요 능력치", "아츠 강도", "방출"],
    "바다와 별의 꿈★": ["지능", "치유 효율", "고통"],
    "사명의 길★": ["의지", "궁충", "추격"],
    "작품: 침식 흔적★": ["의지", "자연 피해", "억제"],
    "O.B.J. 아츠 아이덴티티": ["지능", "아츠 강도", "추격"],
    "선교의 자유": ["의지", "치유 효율", "의료"],
    "황무지의 방랑자": ["지능", "전기 피해", "고통"],
    "무가내하": ["의지", "궁충", "사기"],
    "망자의 노래": ["지능", "공격력", "어둠"]
}

# ✅ 해상도별 프리셋 (base_width x base_height: (start_x, start_y, spacing_x, spacing_y))
RESOLUTION_PRESETS = {
    (1280, 768): (82, 97, 105, 110),
    (1920, 1080): (123, 145, 158, 165),  # 1920/1280 = 1.5배
    (1600, 900): (102, 121, 131, 137),   # 1600/1280 = 1.25배
    (2560, 1440): (164, 194, 210, 220),  # 2560/1280 = 2배
    (1366, 768): (87, 97, 112, 110),     # 1366/1280 = 1.067배
}

# 전역 변수
scan_region = None
first_item_pos = None
game_window_rect = None
current_scale = 1.0
lock_button_pos = None
lock_template = None 
lock_button_template = None 
grid_spacing = (105, 110)  # ✅ 동적으로 설정될 간격

GRID_COLS = 4
GRID_ROWS = 5

auto_scan_enabled = False
scan_state = {"current_row": 0, "current_col": 0, "total_scanned": 0, "total_locked": 0}

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
    
    # ✅ 스케일 계산
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
    """단일 값의 스케일 변환"""
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
    """노란색 아이템 감지 - 그리드 자동 설정용"""
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
    if os.path.exists("lock_template.png"):
        lock_template = cv2.imread("lock_template.png", cv2.IMREAD_GRAYSCALE)
    if os.path.exists("lock_button_template.png"):
        lock_button_template = cv2.imread("lock_button_template.png", cv2.IMREAD_GRAYSCALE)
    
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

# ============================================================
# ✅ [핵심 수정] 잠금 여부 감지 함수 - 오탐지 문제 해결
# ============================================================
def is_item_locked_template(item_pos):
    """
    수정된 잠금 아이콘 감지 함수.
    
    기존 문제점:
      1. threshold=0.6 이 너무 낮아 잠금 아이콘이 없는 곳에서도 매칭됨
      2. search_size=60px 이 너무 작아 아이콘이 살짝 벗어나면 영역을 벗어남
      3. offset 계산이 부정확해 엉뚱한 위치(인접 아이템 영역 등)를 검색함
      4. 디버그 로그가 없어 어디를 검색했는지 추적 불가
    
    수정 내용:
      1. threshold 를 0.6 → 0.78 로 상향 (오탐지 방지)
      2. 검색 영역을 아이템 셀 크기 기반으로 명확하게 제한
         - 아이템 중심에서 셀 절반 범위 내부만 검색
         - 인접 아이템 영역과 겹치지 않도록 margin 적용
      3. 잠금 아이콘의 실제 게임 내 위치(좌하단 코너)에 맞게 offset 보정
      4. 디버그 로그 추가 (매칭 점수, 검색 영역 좌표 출력)
    """
    global lock_template
    if lock_template is None:
        return False
    
    try:
        # ── 1. 아이템 셀 크기 기준으로 검색 영역 계산 ──────────────────
        # 아이템 그리드 간격의 절반에서 약간의 여백을 뺀 크기로 검색 범위 제한.
        # 이렇게 하면 인접 아이템의 잠금 아이콘이 섞이는 문제를 원천 차단함.
        cell_half_w = int(grid_spacing[0] * 0.45)   # 셀 가로 절반 (약간 축소)
        cell_half_h = int(grid_spacing[1] * 0.45)   # 셀 세로 절반 (약간 축소)

        # ── 2. 잠금 아이콘의 게임 내 실제 위치 오프셋 보정 ─────────────
        # 엔드필드 인벤토리에서 잠금 아이콘은 아이템 셀의 좌하단에 위치.
        # 기존 코드: item_pos 기준 x-60, y+20 → 잠금 아이콘이 아닌 다른 영역을 검색하는 경우 있음.
        # 수정: 아이템 중심(item_pos)에서 셀 크기 비율로 offset 계산.
        icon_offset_x = -int(grid_spacing[0] * 0.38)  # 아이템 중심 기준 좌측
        icon_offset_y = int(grid_spacing[1] * 0.25)   # 아이템 중심 기준 하단

        icon_center_x = item_pos[0] + icon_offset_x
        icon_center_y = item_pos[1] + icon_offset_y

        # 검색 영역: 아이콘 예상 중심에서 셀 절반 크기만큼만 검색
        search_x1 = icon_center_x - cell_half_w
        search_y1 = icon_center_y - cell_half_h
        search_x2 = icon_center_x + cell_half_w
        search_y2 = icon_center_y + cell_half_h

        # 화면 경계 보정
        search_x1 = max(0, search_x1)
        search_y1 = max(0, search_y1)
        search_bbox = (search_x1, search_y1, search_x2, search_y2)

        # 검색 영역이 너무 작으면 스킵
        if (search_x2 - search_x1) < 10 or (search_y2 - search_y1) < 10:
            print(f"  ⚠️ 검색 영역 너무 작음: {search_bbox}")
            return False

        search_img = ImageGrab.grab(bbox=search_bbox)
        search_gray = cv2.cvtColor(np.array(search_img), cv2.COLOR_RGB2GRAY)

        # ── 3. 템플릿 스케일 조정 ─────────────────────────────────────
        if current_scale != 1.0:
            scaled_w = max(1, int(lock_template.shape[1] * current_scale))
            scaled_h = max(1, int(lock_template.shape[0] * current_scale))
            scaled_template = cv2.resize(lock_template, (scaled_w, scaled_h))
        else:
            scaled_template = lock_template

        # 템플릿이 검색 영역보다 크면 감지 불가
        if (scaled_template.shape[1] > search_gray.shape[1] or
                scaled_template.shape[0] > search_gray.shape[0]):
            print(f"  ⚠️ 템플릿({scaled_template.shape[1]}x{scaled_template.shape[0]})이 "
                  f"검색영역({search_gray.shape[1]}x{search_gray.shape[0]})보다 큼 → 잠금 안됨 처리")
            return False

        result = cv2.matchTemplate(search_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # ── 4. 디버그 로그 ─────────────────────────────────────────────
        is_locked = max_val >= 0.78  # ✅ threshold 0.6 → 0.78 상향
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
        
        if len(yellow_bars) < 1: return
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
    except: pass

def auto_detect_grid():
    """✅ 개선된 그리드 자동 감지: 실제 노란색 아이템을 찾아서 설정"""
    global first_item_pos, grid_spacing
    
    try:
        status_label.config(text="🔍 아이템 그리드 감지 중...", fg="#f39c12")
        root.update()
        
        # 1단계: 프리셋 확인
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
            # 2단계: 스케일 기반 계산
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
        
        # 3단계: 실제 아이템 감지로 검증 및 보정
        detected_items = detect_yellow_items()
        
        if len(detected_items) >= 4:
            # 왼쪽 상단 영역의 아이템들만 필터링 (화면의 상위 40%, 좌측 60%)
            left_top_items = [
                item for item in detected_items
                if item[0] < game_window_rect['x'] + game_window_rect['width'] * 0.6
                and item[1] < game_window_rect['y'] + game_window_rect['height'] * 0.4
            ]
            
            if len(left_top_items) >= 4:
                # 가장 왼쪽 상단 아이템 찾기
                left_top_items.sort(key=lambda p: p[0] + p[1])
                detected_first = left_top_items[0]
                
                # 감지된 위치와 계산된 위치의 차이 확인
                diff_x = abs(detected_first[0] - first_item_pos[0])
                diff_y = abs(detected_first[1] - first_item_pos[1])
                
                # 차이가 크면 감지된 위치 사용
                if diff_x > 20 or diff_y > 20:
                    print(f"⚠️ 계산 위치와 감지 위치 차이 큼: ({diff_x}, {diff_y})")
                    print(f"   계산: {first_item_pos} -> 감지: {detected_first}")
                    first_item_pos = detected_first
                    
                    # 간격도 실제 아이템들로 재계산
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
        
        # 상대 좌표 계산 (디버깅용)
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
    """그리드 위치로 아이템 좌표 계산"""
    if not first_item_pos: 
        return None
    
    x = first_item_pos[0] + (col * grid_spacing[0])
    y = first_item_pos[1] + (row * grid_spacing[1])
    
    return (x, y)

def preprocess_image_method1(img):
    """방법 1: 기본 이진화"""
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    scale = 2 if current_scale < 1.5 else 3
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    inverted = cv2.bitwise_not(resized)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binary)

def preprocess_image_method2(img):
    """방법 2: 적응형 이진화"""
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    scale = 2 if current_scale < 1.5 else 3
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    inverted = cv2.bitwise_not(resized)
    binary = cv2.adaptiveThreshold(inverted, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    return Image.fromarray(binary)

def preprocess_image_method3(img):
    """방법 3: 대비 강화"""
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
    """병렬 OCR 처리"""
    try:
        region_key = str(region)
        with cache_lock:
            if region_key in ocr_cache:
                cache_time, result = ocr_cache[region_key]
                if time.time() - cache_time < 1.0:
                    return result
        
        img = ImageGrab.grab(bbox=region)
        
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
                
                if len(clean_text) > 20:
                    break
                    
            except Exception as e:
                print(f"⚠️ 전처리 방법 {idx+1} 실패: {str(e)}")
                continue
        
        combined_text = ' '.join(all_results)
        
        if not combined_text:
            print(f"❌ OCR 완전 실패")
            return []
        
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
            ocr_cache[region_key] = (time.time(), found_kor)
            if len(ocr_cache) > 50:
                oldest = min(ocr_cache.items(), key=lambda x: x[1][0])
                del ocr_cache[oldest[0]]
        
        return found_kor
    except Exception as e:
        print(f"❌ OCR 오류: {str(e)}")
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
    
    if not is_item_at_position(item_pos):
        print(f"⚠️ [{row},{col}] 아이템 없음 - 스캔 종료")
        status_label.config(text="✅ 스캔 종료 (빈 공간)", fg="#2ecc71")
        stop_scan_ui()
        return
    
    if is_item_locked_template(item_pos):
        print(f"🔒 [{row},{col}] 이미 잠금됨 - 건너뜀")
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
    
    print(f"✅ 아이템 감지됨 - 클릭하여 옵션 확인")
    click_position(item_pos)
    time.sleep(0.3)
    
    detected_options = scan_options()
    
    if not detected_options:
        print(f"⚠️ OCR 1차 실패 - 0.2초 후 재시도")
        time.sleep(0.2)
        detected_options = scan_options()
    
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
                print(f"⚠️ 잠금 버튼 찾기 실패")
        else: 
            match_label.config(text="❌ 일치 없음", fg="#95a5a6")
            print(f"❌ 무기 매칭 실패")
    else: 
        option_label.config(text="❌ OCR 실패 (2회)", fg="#e74c3c")
        print(f"❌ 옵션 인식 완전 실패")
    
    scan_state["total_scanned"] += 1
    scan_state["current_col"] += 1
    if scan_state["current_col"] >= GRID_COLS:
        scan_state["current_col"] = 0
        scan_state["current_row"] += 1
    
    progress_label.config(text=f"진행: {scan_state['total_scanned']}/20 | 잠금: {scan_state['total_locked']}")
    root.after(250, scan_loop)

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

def manual_adjust_position():
    """✅ 수동 위치 조정 기능"""
    def save_adjustment():
        global first_item_pos, grid_spacing
        try:
            x_offset = int(x_entry.get())
            y_offset = int(y_entry.get())
            spacing_x = int(spacing_x_entry.get())
            spacing_y = int(spacing_y_entry.get())
            
            # 현재 위치에 오프셋 적용
            if first_item_pos:
                first_item_pos = (first_item_pos[0] + x_offset, first_item_pos[1] + y_offset)
            
            grid_spacing = (spacing_x, spacing_y)
            
            rel_x = first_item_pos[0] - game_window_rect['x']
            rel_y = first_item_pos[1] - game_window_rect['y']
            
            auto_setup_label.config(
                text=f"✅ 기준점(수동): 창내({rel_x},{rel_y}) / 화면{first_item_pos}",
                fg="#3498db"
            )
            spacing_label.config(
                text=f"✅ 간격(수동): 가로 {grid_spacing[0]}px, 세로 {grid_spacing[1]}px",
                fg="#3498db"
            )
            
            adjust_window.destroy()
            messagebox.showinfo("완료", "위치가 수동으로 조정되었습니다!")
        except:
            messagebox.showerror("오류", "올바른 숫자를 입력하세요")
    
    adjust_window = tk.Toplevel(root)
    adjust_window.title("수동 위치 조정")
    adjust_window.geometry("400x300")
    
    tk.Label(adjust_window, text="기준점 오프셋 (현재 위치 기준)", font=("Malgun Gothic", 10, "bold")).pack(pady=10)
    
    offset_frame = tk.Frame(adjust_window)
    offset_frame.pack(pady=5)
    tk.Label(offset_frame, text="X 오프셋:").grid(row=0, column=0, padx=5)
    x_entry = tk.Entry(offset_frame, width=10)
    x_entry.insert(0, "0")
    x_entry.grid(row=0, column=1, padx=5)
    
    tk.Label(offset_frame, text="Y 오프셋:").grid(row=1, column=0, padx=5)
    y_entry = tk.Entry(offset_frame, width=10)
    y_entry.insert(0, "0")
    y_entry.grid(row=1, column=1, padx=5)
    
    tk.Label(adjust_window, text="그리드 간격 (픽셀)", font=("Malgun Gothic", 10, "bold")).pack(pady=10)
    
    spacing_frame = tk.Frame(adjust_window)
    spacing_frame.pack(pady=5)
    tk.Label(spacing_frame, text="가로 간격:").grid(row=0, column=0, padx=5)
    spacing_x_entry = tk.Entry(spacing_frame, width=10)
    spacing_x_entry.insert(0, str(grid_spacing[0]))
    spacing_x_entry.grid(row=0, column=1, padx=5)
    
    tk.Label(spacing_frame, text="세로 간격:").grid(row=1, column=0, padx=5)
    spacing_y_entry = tk.Entry(spacing_frame, width=10)
    spacing_y_entry.insert(0, str(grid_spacing[1]))
    spacing_y_entry.grid(row=1, column=1, padx=5)
    
    tk.Button(adjust_window, text="적용", command=save_adjustment, bg="#3498db", fg="white").pack(pady=20)
    tk.Label(adjust_window, text="💡 자동 감지가 정확하지 않을 때 사용하세요", 
             font=("Malgun Gothic", 8), fg="#7f8c8d").pack()

def on_key_press(key):
    try:
        if key == keyboard.Key.f1: toggle_auto_scan()
        elif key == keyboard.Key.f2: stop_scan_ui()
    except: pass

keyboard.Listener(on_press=on_key_press).start()

root = tk.Tk()
root.title("Endfield Auto Scanner v7.1 (Lock Fix)")
root.geometry("540x880")
root.attributes("-topmost", True)
style = ttk.Style()
style.configure("Running.TButton", foreground="#e74c3c")

f = tk.Frame(root, padx=20, pady=20, bg="#ecf0f1")
f.pack(fill="both", expand=True)

tk.Label(f, text="엔드필드 자동 잠금 (다중 해상도)", font=("Malgun Gothic", 16, "bold"), bg="#ecf0f1").pack(pady=10)

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

auto_btn = ttk.Button(f, text="▶️ 자동 스캔 시작 (F1)", command=toggle_auto_scan)
auto_btn.pack(pady=10, fill="x")

# ✅ 수동 조정 버튼 추가
manual_btn = ttk.Button(f, text="🔧 수동 위치 조정", command=manual_adjust_position)
manual_btn.pack(pady=5, fill="x")

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

# ✅ 도움말 추가
help_frame = tk.LabelFrame(f, text="💡 도움말", bg="white", padx=10, pady=5)
help_frame.pack(fill="x", pady=5)
tk.Label(help_frame, text="• 1920x1080, 1280x768 등 자동 지원", bg="white", anchor="w", font=("Malgun Gothic", 8)).pack(anchor="w")
tk.Label(help_frame, text="• 자동 감지 실패 시 '수동 위치 조정' 사용", bg="white", anchor="w", font=("Malgun Gothic", 8)).pack(anchor="w")
tk.Label(help_frame, text="• F1: 스캔 시작/중지, F2: 강제 중지", bg="white", anchor="w", font=("Malgun Gothic", 8)).pack(anchor="w")

root.after(100, load_lock_template)
root.mainloop()
