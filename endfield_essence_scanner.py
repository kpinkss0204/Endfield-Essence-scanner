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

# 전역 변수
scan_region = None
first_item_pos = None
game_window_rect = None  # 게임 창 영역 (x, y, width, height)
base_resolution = (1280, 768)  # 기준 해상도
item_spacing = (104, 110)  # 기준 해상도 기준 간격
current_scale = 1.0  # 현재 스케일링 비율
lock_button_pos = None
lock_template = None 
lock_button_template = None 

GRID_COLS = 4
GRID_ROWS = 5

auto_scan_enabled = False
scan_state = {"current_row": 0, "current_col": 0, "total_scanned": 0, "total_locked": 0}

def find_game_window():
    """게임 창을 찾아서 영역 반환 (타이틀에 'endfield' 또는 '엔드필드' 포함)"""
    global game_window_rect, current_scale
    
    def enum_windows_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            # 자기 자신(Auto Scanner) 제외 및 게임 관련 키워드만 검색
            if title and ('scanner' not in title.lower() and 'auto' not in title.lower()):
                if 'endfield' in title.lower() or '엔드필드' in title or '명日方舟' in title:
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    # 너무 작은 창 제외 (최소 800x600)
                    if width >= 800 and height >= 600:
                        windows.append((hwnd, title, width, height))
                        print(f"🔍 발견된 게임 창: '{title}' ({width}x{height})")
    
    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    
    print(f"📊 총 {len(windows)}개의 게임 창 발견")
    
    if not windows:
        game_window_label.config(text="❌ 게임 창을 찾을 수 없습니다", fg="#e74c3c")
        status_label.config(text="💡 게임을 먼저 실행하세요", fg="#f39c12")
        print("⚠️ 게임 창 검색 실패 - 타이틀에 'endfield', '엔드필드', '명日方舟' 포함 필요")
        return False
    
    # 가장 큰 창 선택 (게임 창일 가능성이 높음)
    windows.sort(key=lambda x: x[2] * x[3], reverse=True)
    hwnd, title, width, height = windows[0]
    
    print(f"✅ 선택된 창: '{title}' ({width}x{height})")
    
    rect = win32gui.GetWindowRect(hwnd)
    x, y, x2, y2 = rect
    
    # 클라이언트 영역 가져오기 (타이틀바 제외)
    try:
        client_rect = win32gui.GetClientRect(hwnd)
        client_width = client_rect[2]
        client_height = client_rect[3]
        
        # 클라이언트 좌표를 스크린 좌표로 변환
        client_pos = win32gui.ClientToScreen(hwnd, (0, 0))
        
        game_window_rect = {
            'x': client_pos[0],
            'y': client_pos[1],
            'width': client_width,
            'height': client_height
        }
    except:
        # 실패 시 대략적인 보정값 사용
        title_bar_height = 30
        border_width = 8
        
        game_window_rect = {
            'x': x + border_width,
            'y': y + title_bar_height,
            'width': width - border_width * 2,
            'height': height - title_bar_height - border_width
        }
    
    # 스케일 계산 (기준: 1280x768)
    scale_x = game_window_rect['width'] / base_resolution[0]
    scale_y = game_window_rect['height'] / base_resolution[1]
    current_scale = (scale_x + scale_y) / 2  # 평균 스케일 사용
    
    game_window_label.config(
        text=f"✅ '{title[:30]}...' {game_window_rect['width']}x{game_window_rect['height']} ({current_scale:.2f}x)",
        fg="#27ae60"
    )
    
    print(f"🎮 게임 창 최종 선택: {title}")
    print(f"📏 클라이언트 영역: ({game_window_rect['x']}, {game_window_rect['y']}) {game_window_rect['width']}x{game_window_rect['height']}")
    print(f"📐 스케일: {current_scale:.2f}x")
    
    return True

def get_scaled_spacing():
    """현재 스케일에 맞는 아이템 간격 반환"""
    return (
        int(item_spacing[0] * current_scale),
        int(item_spacing[1] * current_scale)
    )

def is_point_in_game_window(x, y):
    """좌표가 게임 창 안에 있는지 확인"""
    if not game_window_rect:
        return True  # 게임 창을 못 찾은 경우 모든 좌표 허용
    
    return (game_window_rect['x'] <= x <= game_window_rect['x'] + game_window_rect['width'] and
            game_window_rect['y'] <= y <= game_window_rect['y'] + game_window_rect['height'])

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
        # 게임 창 영역만 스크린샷
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
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 40 and h < 15:
                # 오프셋 적용하여 절대 좌표로 변환
                item_center = (offset_x + x + w//2, offset_y + y - 60)
                detected_points.append(item_center)
        return detected_points
    except: 
        return []

def is_item_at_position(target_pos, tolerance=70):  # tolerance를 70으로 증가
    detected_items = detect_yellow_items()
    if not detected_items:  # ✅ 아이템이 하나도 없으면 False
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
        # 게임 창 오른쪽 절반만 검색
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
        result = cv2.matchTemplate(search_gray, lock_button_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val >= 0.7:
            h, w = lock_button_template.shape
            return (search_bbox[0] + max_loc[0] + w // 2, search_bbox[1] + max_loc[1] + h // 2)
        return None
    except: return None

def is_item_locked_template(item_pos):
    global lock_template
    if lock_template is None: return False
    try:
        check_x, check_y = item_pos[0] - 60, item_pos[1] + 20
        search_bbox = (check_x, check_y, check_x + 60, check_y + 60)
        search_img = ImageGrab.grab(bbox=search_bbox)
        search_gray = cv2.cvtColor(np.array(search_img), cv2.COLOR_RGB2GRAY)
        result = cv2.matchTemplate(search_gray, lock_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= 0.6
    except: return False

def auto_detect_option_region():
    global scan_region
    try:
        status_label.config(text="🔍 옵션 영역 찾는 중...", fg="#f39c12")
        root.update()
        
        # 게임 창 영역만 스크린샷
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
        lower_yellow = np.array([20, 100, 150]); upper_yellow = np.array([35, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        yellow_bars = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > w and h > 30 and w < 20: yellow_bars.append((x, y, w, h))
        
        if len(yellow_bars) < 1: return
        yellow_bars.sort(key=lambda b: b[1])
        top_3 = yellow_bars[:3]
        
        # 오프셋 적용
        min_x = offset_x + min(b[0] for b in top_3) + 15
        min_y = offset_y + min(b[1] for b in top_3)
        max_x = offset_x + max(b[0] + b[2] for b in top_3) + int(240 * current_scale)
        max_y = offset_y + max(b[1] + b[3] for b in top_3)
        
        scan_region = (min_x, min_y, max_x, max_y)
        scan_region_label.config(text=f"✅ 옵션 영역: ({min_x},{min_y}) ~ ({max_x},{max_y})", fg="#27ae60")
    except: pass

def auto_detect_grid():
    """노란색 등급바를 감지하여 기준점 찾고 현재 해상도에 맞는 간격 계산"""
    try:
        status_label.config(text="🔍 그리드 기준점 찾는 중...", fg="#f39c12")
        root.update()
        
        detected_points = detect_yellow_items()
        if not detected_points:
            status_label.config(text="❌ 아이템을 찾을 수 없습니다!", fg="#e74c3c")
            return

        detected_points.sort(key=lambda p: (p[1], p[0]))
        global first_item_pos
        first_item_pos = detected_points[0]
        
        # 스케일 적용된 간격 계산
        scaled_spacing = get_scaled_spacing()
        
        auto_setup_label.config(text=f"✅ 기준점: ({first_item_pos[0]},{first_item_pos[1]})", fg="#27ae60")
        spacing_label.config(
            text=f"✅ 간격: 가로 {scaled_spacing[0]}px, 세로 {scaled_spacing[1]}px (스케일: {current_scale:.2f}x)",
            fg="#27ae60"
        )
        status_label.config(text="👍 그리드 설정 완료!", fg="#2ecc71")
    except Exception as e:
        status_label.config(text=f"❌ 오류: {str(e)}", fg="#e74c3c")

def get_item_position(row, col):
    if not first_item_pos: return None
    scaled_spacing = get_scaled_spacing()
    return (
        first_item_pos[0] + (col * scaled_spacing[0]),
        first_item_pos[1] + (row * scaled_spacing[1])
    )

def preprocess_image_advanced(img):
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    scale = 3
    resized = cv2.resize(gray, (int(gray.shape[1] * scale), int(gray.shape[0] * scale)), interpolation=cv2.INTER_LINEAR)
    inverted = cv2.bitwise_not(resized)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary = cv2.convertScaleAbs(binary, alpha=1.2, beta=5)
    final = cv2.copyMakeBorder(binary, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    return Image.fromarray(final)

def scan_options():
    try:
        img = ImageGrab.grab(bbox=scan_region)
        processed_img = preprocess_image_advanced(img)
        text1 = pytesseract.image_to_string(processed_img, lang="eng", config=r'--oem 3 --psm 7')
        text2 = pytesseract.image_to_string(processed_img, lang="eng", config=r'--oem 3 --psm 6')
        clean_text = re.sub(r'[^a-zA-Z\s]', ' ', f"{text1} {text2}").lower()
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # ✅ 원본 OCR 텍스트 출력
        print(f"📝 OCR 원본: {clean_text[:100]}")  # 처음 100자만
        
        typo_fixes = {'atlribute': 'attribute', 'altribute': 'attribute', 'atribute': 'attribute', 'criticai': 'critical', 'rale': 'rate'}
        for typo, correct in typo_fixes.items(): 
            clean_text = clean_text.replace(typo, correct)
        
        found_kor = []
        found_raw = []
        sorted_keys = sorted(TARGET_KEYWORDS.keys(), key=len, reverse=True)
        for eng in sorted_keys:
            if eng in found_raw: continue
            if ' ' in eng:
                if eng in clean_text:
                    found_kor.append(TARGET_KEYWORDS[eng])
                    found_raw.append(eng)
            else:
                if re.search(r'\b' + re.escape(eng) + r'\b', clean_text):
                    found_kor.append(TARGET_KEYWORDS[eng])
                    found_raw.append(eng)
        
        # ✅ 인식 결과 상세 출력
        if found_raw:
            print(f"✅ 인식된 영문: {', '.join(found_raw)}")
            print(f"✅ 한글 변환: {', '.join(found_kor)}")
        else:
            print(f"❌ 키워드 매칭 실패 (OCR 텍스트 확인 필요)")
        
        return found_kor
    except Exception as e:
        print(f"❌ OCR 오류: {str(e)}")
        return []

def check_weapon_match(options):
    return [name for name, req in WEAPON_DB.items() if all(opt in options for opt in req)]

def scan_loop():
    global auto_scan_enabled, scan_state
    if not auto_scan_enabled: return
    
    row, col = scan_state["current_row"], scan_state["current_col"]
    if row >= GRID_ROWS:
        status_label.config(text=f"✅ 완료! (총 {scan_state['total_scanned']}개)", fg="#2ecc71")
        stop_scan_ui(); return

    item_pos = get_item_position(row, col)
    
    # ✅ 디버그 정보 추가
    print(f"\n{'='*50}")
    print(f"🔍 [{row},{col}] 스캔 중 - 예상 위치: {item_pos}")
    
    # ✅ 수정: 아이템 존재 여부를 먼저 확인
    if not is_item_at_position(item_pos):
        print(f"⚠️ [{row},{col}] 아이템 없음 - 스캔 종료")
        status_label.config(text="✅ 스캔 종료 (빈 공간)", fg="#2ecc71")
        stop_scan_ui()
        return
    
    # ✅ 핵심 수정: 잠금 체크를 클릭 전으로 이동 (클릭하지 않고 확인)
    if is_item_locked_template(item_pos):
        print(f"🔒 [{row},{col}] 이미 잠금됨 - 클릭 없이 건너뜀")
        match_label.config(text="🔒 이미 잠금됨", fg="#95a5a6")
        option_label.config(text="감지: 건너뜀 (잠금됨)", fg="#95a5a6")
        
        # ✅ 카운트만 증가하고 바로 다음으로
        scan_state["total_scanned"] += 1
        scan_state["current_col"] += 1
        if scan_state["current_col"] >= GRID_COLS:
            scan_state["current_col"] = 0
            scan_state["current_row"] += 1
        
        progress_label.config(text=f"진행: {scan_state['total_scanned']}/20 | 잠금: {scan_state['total_locked']}")
        root.after(400, scan_loop)
        return
    
    # ✅ 잠금되지 않은 아이템만 클릭
    print(f"✅ 아이템 감지됨 - 클릭")
    click_position(item_pos)
    time.sleep(0.3)
    
    detected_options = scan_options()
    if detected_options:
        option_text = ", ".join(detected_options)
        option_label.config(text=f"감지: {option_text}", fg="#27ae60")
        
        matches = check_weapon_match(detected_options)
        if matches:
            match_text = ", ".join(matches)
            match_label.config(text=f"✅ 일치: {match_text}", fg="#27ae60")
            print(f"🎯 매칭 성공: {match_text}")
            
            btn_pos = find_lock_button()
            if btn_pos: 
                click_position(btn_pos)
                scan_state["total_locked"] += 1
                print(f"🔐 잠금 실행")
            else:
                print(f"⚠️ 잠금 버튼 찾기 실패")
        else: 
            match_label.config(text="❌ 일치 없음", fg="#95a5a6")
            print(f"❌ 무기 매칭 실패")
    else: 
        option_label.config(text="감지: 실패", fg="#e74c3c")
        print(f"❌ 옵션 인식 실패")
    
    scan_state["total_scanned"] += 1
    scan_state["current_col"] += 1
    if scan_state["current_col"] >= GRID_COLS:
        scan_state["current_col"] = 0
        scan_state["current_row"] += 1
    
    progress_label.config(text=f"진행: {scan_state['total_scanned']}/20 | 잠금: {scan_state['total_locked']}")
    root.after(400, scan_loop)

def toggle_auto_scan():
    global auto_scan_enabled
    if auto_scan_enabled: stop_scan_ui(); return
    if lock_template is None or lock_button_template is None:
        status_label.config(text="❌ 템플릿 파일 확인 필요!", fg="#e74c3c"); return
    
    # 게임 창 찾기 시도
    if not find_game_window():
        # 게임 창을 못 찾으면 전체 화면 사용 제안
        response = tk.messagebox.askyesno(
            "게임 창 찾기 실패",
            "게임 창을 찾을 수 없습니다.\n\n전체 화면을 대상으로 스캔하시겠습니까?\n(게임이 전체화면 모드이거나 특수한 이름일 경우)"
        )
        if response:
            # 전체 화면 사용
            global game_window_rect, current_scale
            screen = ImageGrab.grab()
            game_window_rect = {
                'x': 0,
                'y': 0,
                'width': screen.width,
                'height': screen.height
            }
            scale_x = screen.width / base_resolution[0]
            scale_y = screen.height / base_resolution[1]
            current_scale = (scale_x + scale_y) / 2
            game_window_label.config(
                text=f"✅ 전체 화면: {screen.width}x{screen.height} (스케일: {current_scale:.2f}x)",
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
root.title("Endfield Auto Scanner v5.1 (Fixed Window Detection)")
root.geometry("520x800"); root.attributes("-topmost", True)
style = ttk.Style(); style.configure("Running.TButton", foreground="#e74c3c")
f = tk.Frame(root, padx=20, pady=20, bg="#ecf0f1"); f.pack(fill="both", expand=True)

tk.Label(f, text="엔드필드 자동 잠금 (동적 해상도)", font=("Malgun Gothic", 16, "bold"), bg="#ecf0f1").pack(pady=10)
setup_frame = tk.LabelFrame(f, text="📊 상태", bg="white", padx=10, pady=10); setup_frame.pack(fill="x", pady=10)
game_window_label = tk.Label(setup_frame, text="게임 창: 대기", bg="white", fg="#95a5a6"); game_window_label.pack(anchor="w")
template_label = tk.Label(setup_frame, text="템플릿 로딩 중...", bg="white", fg="#95a5a6"); template_label.pack(anchor="w")
lock_btn_label = tk.Label(setup_frame, text="버튼 템플릿 로딩 중...", bg="white", fg="#95a5a6"); lock_btn_label.pack(anchor="w")
scan_region_label = tk.Label(setup_frame, text="옵션 영역: 대기", bg="white", fg="#95a5a6"); scan_region_label.pack(anchor="w")
auto_setup_label = tk.Label(setup_frame, text="그리드: 대기", bg="white", fg="#95a5a6"); auto_setup_label.pack(anchor="w")
spacing_label = tk.Label(setup_frame, text="간격: 대기", bg="white", fg="#95a5a6"); spacing_label.pack(anchor="w")

auto_btn = ttk.Button(f, text="▶️ 자동 스캔 시작 (F1)", command=toggle_auto_scan); auto_btn.pack(pady=10, fill="x")
status_label = tk.Label(f, text="⏳ 대기 중...", font=("Malgun Gothic", 12, "bold"), bg="#ecf0f1"); status_label.pack()
progress_label = tk.Label(f, text="진행: 0/20 | 잠금: 0", bg="#ecf0f1"); progress_label.pack()

result_frame = tk.LabelFrame(f, text="📊 실시간 결과", bg="white", padx=10, pady=10); result_frame.pack(fill="both", expand=True, pady=10)
option_label = tk.Label(result_frame, text="감지: -", bg="white", anchor="w"); option_label.pack(fill="x")
match_label = tk.Label(result_frame, text="매칭: -", bg="white", anchor="w"); match_label.pack(fill="x")

root.after(100, load_lock_template)
root.mainloop()
