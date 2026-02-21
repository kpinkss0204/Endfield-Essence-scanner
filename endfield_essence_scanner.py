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
from concurrent.futures import ThreadPoolExecutor, as_completed
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

TESSERACT_LANG, TESSERACT_CONFIG = check_tesseract_language()
USE_KOREAN_OCR = (TESSERACT_LANG == 'kor')

# ============================================================
# 리소스 파일 경로 처리 (exe 빌드 대응)
# ============================================================
def resource_path(relative_path):
    """PyInstaller로 빌드된 exe에서 리소스 파일 경로 찾기"""
    try:
        base_path = sys._MEIPASS
    except Exception:
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

WEAPON_DB = load_json('weapons_db.json')
if WEAPON_DB is None:
    print("❌ weapons_db.json 로드 실패. 프로그램을 종료합니다.")
    exit(1)

# ✅ 해상도별 프리셋
RESOLUTION_PRESETS = {
    (1280, 768):  (82,  97,  105, 110),
    (1920, 1080): (123, 145, 158, 165),
    (1600, 900):  (102, 121, 131, 137),
    (2560, 1440): (164, 194, 210, 220),
    (1366, 768):  (87,  97,  112, 110),
}

# 전역 변수
scan_region         = None
first_item_pos      = None
game_window_rect    = None
current_scale       = 1.0
lock_button_pos     = None
lock_template       = None
lock_button_template    = None
dispose_template        = None
dispose_button_template = None
grid_spacing = (105, 110)

GRID_COLS = 4
GRID_ROWS = 6

auto_scan_enabled = False
scan_state = {
    "current_row": 0,
    "current_col": 0,
    "total_scanned": 0,
    "total_locked": 0,
    "total_disposed": 0,
}

scan_delay_after_click    = 0.4
scan_delay_between_items  = 0.2

# ✅ 잠금/폐기 상태 캐시
lock_status_cache = {}

ocr_cache  = {}
cache_lock = threading.Lock()

scan_log      = []
log_file_path = None

def init_log_file():
    global log_file_path
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file_path = f"scan_result_{timestamp}.txt"

def save_scan_log():
    if not log_file_path or not scan_log:
        return
    try:
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("엔드필드 자동 스캔 결과\n")
            f.write(f"스캔 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            total_scanned  = len([l for l in scan_log if l['status'] not in ('empty',)])
            total_locked   = len([l for l in scan_log if l['locked']])
            total_disposed = len([l for l in scan_log if l.get('disposed', False)])
            total_pre_locked   = len([l for l in scan_log if l['status'] == 'pre_locked'])
            total_pre_disposed = len([l for l in scan_log if l['status'] == 'pre_disposed'])

            f.write("📊 요약\n")
            f.write(f"  - 스캔한 아이템  : {total_scanned}개\n")
            f.write(f"  - 새로 잠금      : {total_locked}개\n")
            f.write(f"  - 새로 폐기      : {total_disposed}개\n")
            f.write(f"  - 이미 잠금됨    : {total_pre_locked}개\n")
            f.write(f"  - 이미 폐기됨    : {total_pre_disposed}개\n")
            f.write("\n" + "=" * 60 + "\n\n")

            for entry in scan_log:
                row, col = entry['position']
                f.write(f"[{row},{col}] ")

                if entry['status'] == 'empty':
                    f.write("빈 슬롯\n\n")
                    continue
                if entry['status'] == 'pre_locked':
                    f.write("🔒 이미 잠금됨 (건너뜀)\n\n")
                    continue
                if entry['status'] == 'pre_disposed':
                    f.write("🗑️ 이미 폐기됨 (건너뜀)\n\n")
                    continue
                if not entry['options']:
                    f.write("❌ OCR 실패\n\n")
                    continue

                f.write(f"\n옵션: {', '.join(entry['options'])}\n")

                if entry['matches']:
                    f.write(f"매칭: {', '.join(entry['matches'])}\n")
                    if entry['locked']:
                        f.write("결과: ✅ 잠금 완료\n")
                    else:
                        f.write("결과: ⚠️ 잠금 실패\n")
                else:
                    f.write("매칭: 없음\n")
                    if entry.get('disposed', False):
                        f.write("결과: 🗑️ 폐기 완료\n")
                    elif entry.get('dispose_failed', False):
                        f.write("결과: ⚠️ 폐기 실패\n")
                    else:
                        f.write("결과: - (잠금/폐기 안함)\n")
                f.write("\n")

            f.write("=" * 60 + "\n스캔 완료\n")

        print(f"✅ 로그 파일 저장 완료: {log_file_path}")
        return log_file_path
    except Exception as e:
        print(f"❌ 로그 저장 실패: {str(e)}")
        return None

# ============================================================
# 한국어 텍스트 보정 함수
# ============================================================
def normalize_korean_text(text):
    import re

    clean = re.sub(r'\s+', '', text)
    clean = re.sub(r'[^\uAC00-\uD7A3]', '', clean)
    if not clean:
        return None

    raw_no_space = re.sub(r'[^\uAC00-\uD7A3\s]', '', text).strip()

    if re.search(r'[효요호]\s*[율률]', raw_no_space):
        if re.search(r'궁\s*[극국]\s*기', raw_no_space) and re.search(r'충\s*[전젼]', raw_no_space):
            return "궁극기 충전 효율"
        elif re.search(r'치\s*[유우]', raw_no_space):
            return "치유 효율"
        else:
            return "효율"

    if re.search(r'[효요호][율률롤윤]', clean):
        if re.search(r'궁[극국귱]', clean) and re.search(r'(충[전젼]|획득)', clean):
            return "궁극기 충전 효율"
        elif re.search(r'치[유우]', clean):
            return "치유 효율"
        else:
            return "효율"

    clean = re.sub(r'(증가|흐가|쿨가|흐쿨|골흐|콜흐|툴골|즘가|승가|즐|증|가|중)$', '', clean)
    clean = re.sub(r'\s+', '', clean)
    if not clean:
        return None

    if re.search(r'궁[극국귱]', clean) and re.search(r'(충[전젼]|획득)', clean):
        return "궁극기 충전 효율"
    if re.search(r'주[요오]|능[력럭]', clean):
        return "주요 능력치"
    if re.search(r'치[명망]|확[률를]', clean) or re.search(r'^치확$', clean):
        return "치확"
    if re.search(r'치[유우]', clean) and re.search(r'[효요][율률롤윤]', clean):
        return "치유 효율"
    if re.search(r'오리지[늄눔넘념]|오리즈|오리츠', clean):
        return "아츠 강도"
    if re.search(r'아[츠즈측].*강[도돠]', clean) or (re.search(r'아[츠즈측]', clean) and re.search(r'강[도돠]', clean)):
        return "아츠 강도"
    if re.search(r'아[츠즈측].*피[해혜]', clean) or (re.search(r'아[츠즈측]', clean) and re.search(r'피[해혜]', clean)):
        return "아츠 피해"
    if re.search(r'걱럭|격턱|공[격걱]|격력|공력|^럭$|^공$|콜굴|콜골|휼콜|드룰', clean):
        return "공격력"
    if re.search(r'생[명멍먕]', clean):
        return "생명력"
    if re.search(r'민[첩접쳡]', clean):
        return "민첩성"
    if re.search(r'지[능늄]|시능|자능', clean):
        return "지능"
    if re.search(r'의[지자]|으지|휼|외지|의치', clean):
        return "의지"
    if re.search(r'^힘$|흐임|그[룹룰옵루]|^[으우]루$|^루$', clean):
        return "힘"
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

    return None

# ============================================================
# 게임 창 감지
# ============================================================
def find_game_window():
    global game_window_rect, current_scale

    def enum_windows_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and ('scanner' not in title.lower() and 'auto' not in title.lower()):
                if 'endfield' in title.lower() or '엔드필드' in title or '明日方舟' in title:
                    rect = win32gui.GetWindowRect(hwnd)
                    width  = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width >= 800 and height >= 600:
                        windows.append((hwnd, title, width, height))
                        print(f"🔍 발견된 게임 창: '{title}' ({width}x{height})")

    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    print(f"📊 총 {len(windows)}개의 게임 창 발견")

    if not windows:
        status_label.config(text="❌ 게임 창을 찾을 수 없습니다", fg="#e74c3c")
        return False

    windows.sort(key=lambda x: x[2] * x[3], reverse=True)
    hwnd, title, width, height = windows[0]
    print(f"✅ 선택된 창: '{title}' ({width}x{height})")

    rect = win32gui.GetWindowRect(hwnd)
    try:
        client_rect = win32gui.GetClientRect(hwnd)
        client_pos  = win32gui.ClientToScreen(hwnd, (0, 0))
        game_window_rect = {
            'x': client_pos[0], 'y': client_pos[1],
            'width': client_rect[2], 'height': client_rect[3],
        }
    except:
        x, y, x2, y2 = rect
        game_window_rect = {
            'x': x + 8, 'y': y + 30,
            'width': width - 16, 'height': height - 38,
        }

    current_scale = game_window_rect['width'] / 1280
    print(f"📏 클라이언트: ({game_window_rect['x']},{game_window_rect['y']}) "
          f"{game_window_rect['width']}x{game_window_rect['height']} | 스케일: {current_scale:.2f}x")
    return True

def get_scaled_value(base_value):
    return int(base_value * current_scale)

def click_position(pos):
    if not pos:
        return False
    x, y = pos
    try:
        win32api.SetCursorPos((x, y))
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.03)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)
        time.sleep(0.03)
        print(f"   🖱️ 클릭 완료: ({x}, {y})")
        return True
    except Exception as e:
        print(f"   ❌ 클릭 실패: {str(e)}")
        return False

# ============================================================
# 황색 아이템 감지
# ============================================================
def detect_yellow_items():
    try:
        if game_window_rect:
            bbox = (
                game_window_rect['x'], game_window_rect['y'],
                game_window_rect['x'] + game_window_rect['width'],
                game_window_rect['y'] + game_window_rect['height'],
            )
            screen   = np.array(ImageGrab.grab(bbox=bbox))
            offset_x = game_window_rect['x']
            offset_y = game_window_rect['y']
        else:
            screen   = np.array(ImageGrab.grab())
            offset_x = offset_y = 0

        hsv          = cv2.cvtColor(screen, cv2.COLOR_RGB2HSV)
        lower_yellow = np.array([15, 150, 150])
        upper_yellow = np.array([35, 255, 255])
        mask         = cv2.inRange(hsv, lower_yellow, upper_yellow)
        contours, _  = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected     = []
        min_width    = get_scaled_value(40)
        max_height   = get_scaled_value(15)
        y_offset     = get_scaled_value(60)

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > min_width and h < max_height:
                detected.append((offset_x + x + w // 2, offset_y + y - y_offset))
        return detected
    except:
        return []

def is_item_at_position(target_pos, tolerance=None):
    if tolerance is None:
        tolerance = get_scaled_value(70)
    for item_pos in detect_yellow_items():
        if (abs(item_pos[0] - target_pos[0]) < tolerance and
                abs(item_pos[1] - target_pos[1]) < tolerance):
            return True
    return False

# ============================================================
# 템플릿 로드 (잠금 + 폐기 모두 로드)
# ============================================================
def load_lock_template():
    global lock_template, lock_button_template, dispose_template, dispose_button_template

    path = resource_path("lock_template.png")
    if os.path.exists(path):
        lock_template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        print("✅ lock_template.png 로드 완료")
    else:
        print("❌ lock_template.png 없음")

    path = resource_path("lock_button_template.png")
    if os.path.exists(path):
        lock_button_template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        print("✅ lock_button_template.png 로드 완료")
    else:
        print("❌ lock_button_template.png 없음")

    path = resource_path("dispose_template.png")
    if os.path.exists(path):
        dispose_template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        print("✅ dispose_template.png 로드 완료")
    else:
        print("⚠️ dispose_template.png 없음 (폐기 감지 비활성)")

    path = resource_path("dispose_button_template.png")
    if os.path.exists(path):
        dispose_button_template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        print("✅ dispose_button_template.png 로드 완료")
    else:
        print("⚠️ dispose_button_template.png 없음 (자동 폐기 비활성)")

# ============================================================
# 잠금 버튼 찾기
# ============================================================
def find_lock_button():
    if lock_button_template is None:
        return None
    try:
        if game_window_rect:
            search_bbox = (
                game_window_rect['x'] + game_window_rect['width'] // 2,
                game_window_rect['y'],
                game_window_rect['x'] + game_window_rect['width'],
                game_window_rect['y'] + game_window_rect['height'],
            )
        else:
            screen = ImageGrab.grab()
            search_bbox = (screen.width // 2, 0, screen.width, screen.height)

        search_gray = cv2.cvtColor(np.array(ImageGrab.grab(bbox=search_bbox)), cv2.COLOR_RGB2GRAY)
        tmpl = _scale_template(lock_button_template)
        result = cv2.matchTemplate(search_gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= 0.7:
            h, w = tmpl.shape
            return (search_bbox[0] + max_loc[0] + w // 2,
                    search_bbox[1] + max_loc[1] + h // 2)
        return None
    except:
        return None

# ============================================================
# ✅ 폐기 버튼 찾기 (우측 빨간 휴지통 버튼)
# ============================================================
def find_dispose_button():
    if dispose_button_template is None:
        return None
    try:
        if game_window_rect:
            search_bbox = (
                game_window_rect['x'] + game_window_rect['width'] // 2,
                game_window_rect['y'],
                game_window_rect['x'] + game_window_rect['width'],
                game_window_rect['y'] + game_window_rect['height'],
            )
        else:
            screen = ImageGrab.grab()
            search_bbox = (screen.width // 2, 0, screen.width, screen.height)

        search_img  = np.array(ImageGrab.grab(bbox=search_bbox))
        search_gray = cv2.cvtColor(search_img, cv2.COLOR_RGB2GRAY)
        search_hsv  = cv2.cvtColor(search_img, cv2.COLOR_RGB2HSV)

        THRESHOLD    = 0.55
        SCALES       = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8]

        best_val = -1
        best_loc = None
        best_wh  = None

        for scale in SCALES:
            tw = max(4, int(dispose_button_template.shape[1] * scale * current_scale))
            th = max(4, int(dispose_button_template.shape[0] * scale * current_scale))
            if tw > search_gray.shape[1] or th > search_gray.shape[0]:
                continue
            tmpl = cv2.resize(dispose_button_template, (tw, th))
            result = cv2.matchTemplate(search_gray, tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_wh  = (tw, th)

        print(f"   🔍 폐기 버튼 멀티스케일 최고 점수: {best_val:.3f}")

        if best_val >= THRESHOLD and best_loc is not None:
            cx = search_bbox[0] + best_loc[0] + best_wh[0] // 2
            cy = search_bbox[1] + best_loc[1] + best_wh[1] // 2
            print(f"   ✅ 템플릿 매칭 성공: ({cx}, {cy})")
            return (cx, cy)

        # ── 색상 폴백 ──
        print(f"   🎨 색상 기반 폴백 시도 (점수 {best_val:.3f} < {THRESHOLD})")
        mask1 = cv2.inRange(search_hsv, np.array([0,   50, 60]), np.array([15,  255, 255]))
        mask2 = cv2.inRange(search_hsv, np.array([160, 50, 60]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(mask1, mask2)

        kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN,  kernel)

        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            best_cnt = max(contours, key=cv2.contourArea)
            area     = cv2.contourArea(best_cnt)
            if area > 20:
                x, y, w, h = cv2.boundingRect(best_cnt)
                cx = search_bbox[0] + x + w // 2
                cy = search_bbox[1] + y + h // 2
                print(f"   🎨 색상 폴백 성공: ({cx}, {cy}) 면적={area:.0f}")
                return (cx, cy)

        print(f"   ❌ 폐기 버튼 탐색 완전 실패")
        return None

    except Exception as e:
        print(f"   ❌ 폐기 버튼 탐색 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================
# 아이템 잠금 여부 확인 (템플릿 매칭)
# ============================================================
def _scale_template(template):
    """current_scale 에 맞게 템플릿 크기 조정"""
    if current_scale == 1.0:
        return template
    scaled_w = max(1, int(template.shape[1] * current_scale))
    scaled_h = max(1, int(template.shape[0] * current_scale))
    return cv2.resize(template, (scaled_w, scaled_h))

def _icon_search_bbox(item_pos, offset_x_ratio=-0.38, offset_y_ratio=0.25):
    """아이콘 주변 검색 영역 좌표 계산"""
    half_w = int(grid_spacing[0] * 0.45)
    half_h = int(grid_spacing[1] * 0.45)
    cx = item_pos[0] + int(grid_spacing[0] * offset_x_ratio)
    cy = item_pos[1] + int(grid_spacing[1] * offset_y_ratio)
    x1 = max(0, cx - half_w)
    y1 = max(0, cy - half_h)
    x2 = cx + half_w
    y2 = cy + half_h
    return (x1, y1, x2, y2)

def _match_template_in_region(bbox, template, threshold=0.78):
    """지정 영역에서 템플릿 매칭 점수가 threshold 이상인지 반환"""
    try:
        if (bbox[2] - bbox[0]) < 10 or (bbox[3] - bbox[1]) < 10:
            return False
        search_gray = cv2.cvtColor(np.array(ImageGrab.grab(bbox=bbox)), cv2.COLOR_RGB2GRAY)
        tmpl = _scale_template(template)
        if tmpl.shape[1] > search_gray.shape[1] or tmpl.shape[0] > search_gray.shape[0]:
            return False
        result = cv2.matchTemplate(search_gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= threshold
    except:
        return False

def is_item_locked_template(item_pos):
    if lock_template is None:
        return False
    bbox = _icon_search_bbox(item_pos, offset_x_ratio=-0.38, offset_y_ratio=0.25)
    return _match_template_in_region(bbox, lock_template, threshold=0.78)

# ============================================================
# ✅ 수정된 아이템 폐기 여부 확인
#
# 문제: dispose_template이 lock_template(잠금 아이콘)에도
#       0.72~0.73 점수로 매칭되어 잠금 아이템을 폐기로 오인식
#
# 해결 방법 (3단계 검증):
#   1. dispose_template threshold를 0.40 → 0.55로 상향 (1차 필터)
#   2. lock_template과 교차검증:
#      dispose 점수가 lock 점수보다 LOCK_MARGIN(0.08) 이상 높아야 통과
#   3. 빨간색 픽셀 비율 검증:
#      폐기 마크는 빨간색, 잠금 아이콘은 흰색/회색이므로
#      빨간 픽셀이 5% 미만이면 폐기 마크 아님으로 최종 판단
# ============================================================
def is_item_disposed_template(item_pos):
    """
    아이템 슬롯 좌하단의 폐기(빨간 휴지통) 마크를 확인합니다.

    ✅ 색상 기반 감지만 사용:
      - 그레이스케일 템플릿 매칭은 lock/dispose 아이콘이 위치가 같아
        점수가 항상 비슷하게 나와 구분 불가 → 완전히 제거
      - 폐기 마크 = 빨간색, 잠금 아이콘 = 흰색/회색 이라는
        색상 차이만으로 판단 (훨씬 신뢰성 높음)
      - 아이콘 영역의 빨간 픽셀 수가 임계값 이상이면 폐기로 판단
    """
    # 아이콘 위치: 아이템 슬롯 좌하단 고정
    bbox = _icon_search_bbox(item_pos, offset_x_ratio=-0.38, offset_y_ratio=0.25)

    if (bbox[2] - bbox[0]) < 5 or (bbox[3] - bbox[1]) < 5:
        return False

    # 빨간 픽셀이 이 수 이상이면 폐기 마크로 판단
    # (아이콘 크기에 비례 — 기본 영역 약 90×90px 기준 50픽셀)
    RED_PIXEL_MIN = max(30, int(grid_spacing[0] * grid_spacing[1] * 0.005))

    try:
        region_img = np.array(ImageGrab.grab(bbox=bbox))
        hsv        = cv2.cvtColor(region_img, cv2.COLOR_RGB2HSV)

        # HSV 빨간색 범위 (색상환 양쪽 끝: 0~12도, 168~180도)
        red_mask1 = cv2.inRange(hsv, np.array([0,   100, 80]), np.array([12,  255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([168, 100, 80]), np.array([180, 255, 255]))
        red_mask  = cv2.bitwise_or(red_mask1, red_mask2)

        # 노이즈 제거
        kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)

        red_pixels   = cv2.countNonZero(red_mask)
        total_pixels = region_img.shape[0] * region_img.shape[1]
        red_ratio    = red_pixels / total_pixels if total_pixels > 0 else 0

        print(f"   🎨 빨간 픽셀: {red_pixels}개 (최소:{RED_PIXEL_MIN}) 비율:{red_ratio:.3f}")

        if red_pixels >= RED_PIXEL_MIN:
            print(f"   ✅ 폐기 마크 감지 성공 (빨간 픽셀 {red_pixels}개)")
            return True
        else:
            print(f"   ❌ 빨간 픽셀 부족 → 폐기 마크 없음")
            return False

    except Exception as e:
        print(f"   ❌ 폐기 마크 탐색 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================
# 옵션 영역 자동 감지
# ============================================================
def auto_detect_option_region():
    global scan_region
    try:
        status_label.config(text="🔍 옵션 영역 찾는 중...", fg="#f39c12")
        root.update()

        if game_window_rect:
            bbox = (
                game_window_rect['x'], game_window_rect['y'],
                game_window_rect['x'] + game_window_rect['width'],
                game_window_rect['y'] + game_window_rect['height'],
            )
            screen   = np.array(ImageGrab.grab(bbox=bbox))
            offset_x = game_window_rect['x']
            offset_y = game_window_rect['y']
        else:
            screen   = np.array(ImageGrab.grab())
            offset_x = offset_y = 0

        hsv = cv2.cvtColor(screen, cv2.COLOR_RGB2HSV)
        yellow_mask = cv2.inRange(hsv, np.array([20, 100, 150]), np.array([35, 255, 255]))
        contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_h = get_scaled_value(30)
        max_w = get_scaled_value(20)
        bars  = [(x, y, w, h) for cnt in contours
                 for x, y, w, h in [cv2.boundingRect(cnt)]
                 if h > w and h > min_h and w < max_w]

        if len(bars) < 1:
            scan_region = (
                game_window_rect['x'] + get_scaled_value(560),
                game_window_rect['y'] + get_scaled_value(200),
                game_window_rect['x'] + get_scaled_value(820),
                game_window_rect['y'] + get_scaled_value(450),
            )
            return

        bars.sort(key=lambda b: b[1])
        top3    = bars[:3]
        padding = get_scaled_value(15)
        ext_w   = get_scaled_value(240)

        scan_region = (
            offset_x + min(b[0] for b in top3) + padding,
            offset_y + min(b[1] for b in top3),
            offset_x + max(b[0] + b[2] for b in top3) + ext_w,
            offset_y + max(b[1] + b[3] for b in top3),
        )
        print(f"✅ 옵션 영역 감지 성공: {scan_region}")
    except Exception as e:
        print(f"❌ 옵션 영역 감지 오류: {str(e)}")
        scan_region = (
            game_window_rect['x'] + get_scaled_value(560),
            game_window_rect['y'] + get_scaled_value(200),
            game_window_rect['x'] + get_scaled_value(820),
            game_window_rect['y'] + get_scaled_value(450),
        )

# ============================================================
# 그리드 자동 감지
# ============================================================
def auto_detect_grid():
    global first_item_pos, grid_spacing

    try:
        status_label.config(text="🔍 아이템 그리드 감지 중...", fg="#f39c12")
        root.update()

        res_key      = (game_window_rect['width'], game_window_rect['height'])
        preset_found = False

        for preset_res, preset_vals in RESOLUTION_PRESETS.items():
            if abs(res_key[0] - preset_res[0]) < 50 and abs(res_key[1] - preset_res[1]) < 50:
                start_x, start_y, spacing_x, spacing_y = preset_vals
                first_item_pos = (game_window_rect['x'] + start_x,
                                  game_window_rect['y'] + start_y)
                grid_spacing   = (spacing_x, spacing_y)
                preset_found   = True
                print(f"✅ 프리셋 사용: {preset_res}")
                break

        if not preset_found:
            first_item_pos = (
                game_window_rect['x'] + get_scaled_value(82),
                game_window_rect['y'] + get_scaled_value(97),
            )
            grid_spacing = (get_scaled_value(105), get_scaled_value(110))

        detected = detect_yellow_items()
        if len(detected) >= 4:
            lt = [d for d in detected
                  if d[0] < game_window_rect['x'] + game_window_rect['width']  * 0.6
                  and d[1] < game_window_rect['y'] + game_window_rect['height'] * 0.4]
            if len(lt) >= 4:
                lt.sort(key=lambda p: p[0] + p[1])
                df = lt[0]
                if abs(df[0] - first_item_pos[0]) > 20 or abs(df[1] - first_item_pos[1]) > 20:
                    first_item_pos = df
                    sx = sorted(lt, key=lambda p: p[0])
                    sy = sorted(lt, key=lambda p: p[1])
                    if len(sx) >= 2:
                        grid_spacing = (int(np.median([sx[i+1][0]-sx[i][0] for i in range(min(3,len(sx)-1))])),
                                        grid_spacing[1])
                    if len(sy) >= 2:
                        grid_spacing = (grid_spacing[0],
                                        int(np.median([sy[i+1][1]-sy[i][1] for i in range(min(3,len(sy)-1))])))

        print(f"📍 첫 아이템: {first_item_pos} | 간격: {grid_spacing}")
        status_label.config(text="⏳ 대기 중...", fg="#95a5a6")
    except Exception as e:
        status_label.config(text=f"❌ 오류: {str(e)}", fg="#e74c3c")

def get_item_position(row, col):
    if not first_item_pos:
        return None
    return (first_item_pos[0] + col * grid_spacing[0],
            first_item_pos[1] + row * grid_spacing[1])

# ============================================================
# ✅ 전체 그리드 사전 스캔 (잠금 + 폐기 동시 확인)
# ============================================================
def pre_scan_all_locks():
    global lock_status_cache
    lock_status_cache.clear()

    print("\n" + "=" * 60)
    print("🔍 전체 그리드 잠금/폐기 상태 사전 스캔 시작")
    print("=" * 60)
    status_label.config(text="🔍 잠금/폐기 상태 확인 중...", fg="#f39c12")
    root.update()

    total_items    = 0
    locked_items   = 0
    disposed_items = 0

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            item_pos = get_item_position(row, col)

            if not is_item_at_position(item_pos):
                print(f"⚠️ [{row},{col}] 아이템 없음 - 스캔 종료")
                lock_status_cache[(row, col)] = "empty"
                status_label.config(
                    text=f"✅ 사전 스캔 완료 (잠금:{locked_items} 폐기:{disposed_items}/{total_items})",
                    fg="#2ecc71")
                return total_items, locked_items, disposed_items

            total_items += 1

            # ── 잠금 확인 ──
            if is_item_locked_template(item_pos):
                lock_status_cache[(row, col)] = "locked"
                locked_items += 1
                print(f"🔒 [{row},{col}] 잠금됨")
            # ── 폐기 확인 (잠금이 아닐 때만) ──
            elif is_item_disposed_template(item_pos):
                lock_status_cache[(row, col)] = "disposed"
                disposed_items += 1
                print(f"🗑️ [{row},{col}] 폐기됨")
            else:
                lock_status_cache[(row, col)] = "unlocked"
                print(f"🔓 [{row},{col}] 잠금/폐기 안됨")

            progress_label.config(
                text=f"사전 확인: {total_items}/24 | 잠금:{locked_items} 폐기:{disposed_items}")
            root.update()
            time.sleep(0.03)

    status_label.config(
        text=f"✅ 사전 스캔 완료 (잠금:{locked_items} 폐기:{disposed_items}/{total_items})",
        fg="#2ecc71")
    print(f"\n✅ 사전 스캔 완료: 총 {total_items}개 | 잠금 {locked_items} | 폐기 {disposed_items}\n")
    return total_items, locked_items, disposed_items

# ============================================================
# OCR
# ============================================================
def preprocess_image_fast(img):
    arr    = np.array(img)
    gray   = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if len(arr.shape) == 3 else arr
    resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    inv    = cv2.bitwise_not(resized)
    _, bin_ = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(bin_)

def scan_options_single(region, position=None):
    try:
        region_key = str(region)
        with cache_lock:
            if region_key in ocr_cache:
                ct, result = ocr_cache[region_key]
                if time.time() - ct < 1.0:
                    print("📦 캐시 사용")
                    return result

        test_img = ImageGrab.grab(bbox=region)
        if np.mean(np.array(test_img)) < 10:
            print("⚠️ 이미지 너무 어두움")
            return []

        img  = ImageGrab.grab(bbox=region)
        proc = preprocess_image_fast(img)
        text = pytesseract.image_to_string(proc, lang=TESSERACT_LANG, config=TESSERACT_CONFIG)

        if text.strip():
            print(f"🔍 원본 OCR: {repr(text.strip())}")

        compound_keywords = ["궁극기 충전 효율", "치유 효율"]
        found  = []
        seen   = set()

        if text.strip():
            lines    = text.split('\n')
            all_kw   = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                merged = re.sub(r'\s+', '', line)
                norm   = normalize_korean_text(line) or normalize_korean_text(merged)
                if norm:
                    all_kw.append(norm)

            full_norm = normalize_korean_text(re.sub(r'\s+', '', text))
            if full_norm in compound_keywords and full_norm not in all_kw:
                all_kw.insert(0, full_norm)

            for kw in all_kw:
                if kw in compound_keywords and kw not in seen:
                    found.append(kw); seen.add(kw)

            has_compound = any(k in seen for k in compound_keywords)
            for kw in all_kw:
                if kw not in seen:
                    if kw == "효율" and has_compound:
                        continue
                    found.append(kw); seen.add(kw)

        if not found:
            print("❌ OCR 키워드 없음")
            return []

        print(f"✅ 최종 인식: {', '.join(found)}")

        with cache_lock:
            ocr_cache[region_key] = (time.time(), found)
            if len(ocr_cache) > 50:
                oldest = min(ocr_cache.items(), key=lambda x: x[1][0])
                del ocr_cache[oldest[0]]

        return found
    except Exception as e:
        print(f"❌ OCR 오류: {str(e)}")
        return []

def scan_options(position=None):
    return scan_options_single(scan_region, position)

def check_weapon_match(options):
    matched = []
    for name, req_opts in WEAPON_DB.items():
        if name.startswith('_comment'):
            continue
        if all(opt in options for opt in req_opts):
            matched.append(name)
            print(f"   🎯 매칭: {name} (필요: {', '.join(req_opts)})")
    return matched

# ============================================================
# ✅ 메인 스캔 루프
# ============================================================
def scan_loop():
    global auto_scan_enabled, scan_state

    if not auto_scan_enabled:
        return

    row, col = scan_state["current_row"], scan_state["current_col"]

    if row >= GRID_ROWS:
        status_label.config(
            text=f"✅ 완료! (스캔:{scan_state['total_scanned']} 잠금:{scan_state['total_locked']} 폐기:{scan_state['total_disposed']})",
            fg="#2ecc71")
        stop_scan_ui()
        saved = save_scan_log()
        if saved:
            messagebox.showinfo("스캔 완료",
                f"스캔 완료!\n\n"
                f"잠금: {scan_state['total_locked']}개\n"
                f"폐기: {scan_state['total_disposed']}개\n\n"
                f"로그: {saved}")
        return

    item_pos     = get_item_position(row, col)
    cache_status = lock_status_cache.get((row, col), None)

    print(f"\n{'='*50}")
    print(f"🔍 [{row},{col}] 스캔 | 위치: {item_pos} | 캐시: {cache_status}")

    # ── 빈 슬롯 ──
    if cache_status == "empty":
        print(f"⚠️ [{row},{col}] 빈 슬롯 - 종료")
        scan_log.append({'position': (row, col), 'status': 'empty',
                         'options': [], 'matches': [], 'locked': False})
        stop_scan_ui()
        saved = save_scan_log()
        if saved:
            messagebox.showinfo("스캔 완료", f"스캔 완료!\n\n로그: {saved}")
        return

    # ── 이미 잠금됨 → 건너뜀 ──
    if cache_status == "locked":
        print(f"🔒 [{row},{col}] 이미 잠금됨 - 건너뜀")
        match_label.config(text="🔒 이미 잠금됨", fg="#95a5a6")
        option_label.config(text="건너뜀 (잠금)", fg="#95a5a6")
        scan_log.append({'position': (row, col), 'status': 'pre_locked',
                         'options': [], 'matches': [], 'locked': False})
        _advance_and_next(100)
        return

    # ── 이미 폐기됨 → 건너뜀 ──
    if cache_status == "disposed":
        print(f"🗑️ [{row},{col}] 이미 폐기됨 - 건너뜀")
        match_label.config(text="🗑️ 이미 폐기됨", fg="#95a5a6")
        option_label.config(text="건너뜀 (폐기)", fg="#95a5a6")
        scan_log.append({'position': (row, col), 'status': 'pre_disposed',
                         'options': [], 'matches': [], 'locked': False})
        _advance_and_next(100)
        return

    # ── 실시간 존재 확인 ──
    if not is_item_at_position(item_pos):
        print(f"⚠️ [{row},{col}] 아이템 없음 - 종료")
        scan_log.append({'position': (row, col), 'status': 'empty',
                         'options': [], 'matches': [], 'locked': False})
        stop_scan_ui()
        saved = save_scan_log()
        if saved:
            messagebox.showinfo("스캔 완료", f"스캔 완료!\n\n로그: {saved}")
        return

    # ── 아이템 클릭 ──
    click_position(item_pos)
    time.sleep(0.15)
    try:
        win32api.SetCursorPos((0, 0))
    except:
        pass
    time.sleep(scan_delay_after_click)

    # ── ✅ 클릭 후 실시간 잠금/폐기 재확인 ──
    # 사전 스캔에서 놓쳤을 경우를 대비해 클릭 후 다시 확인
    if is_item_locked_template(item_pos):
        print(f"🔒 [{row},{col}] 클릭 후 재확인: 잠금됨 → 건너뜀")
        match_label.config(text="🔒 잠금됨 (재확인)", fg="#95a5a6")
        option_label.config(text="건너뜀 (잠금 재확인)", fg="#95a5a6")
        scan_log.append({'position': (row, col), 'status': 'pre_locked',
                         'options': [], 'matches': [], 'locked': False})
        _advance_and_next(100)
        return

    if is_item_disposed_template(item_pos):
        print(f"🗑️ [{row},{col}] 클릭 후 재확인: 폐기됨 → 건너뜀")
        match_label.config(text="🗑️ 폐기됨 (재확인)", fg="#95a5a6")
        option_label.config(text="건너뜀 (폐기 재확인)", fg="#95a5a6")
        scan_log.append({'position': (row, col), 'status': 'pre_disposed',
                         'options': [], 'matches': [], 'locked': False})
        _advance_and_next(100)
        return

    # ── OCR 시도 (최대 2회) ──
    detected_options = []
    for attempt in range(2):
        if attempt > 0:
            print(f"🔄 OCR 재시도 {attempt}")
            time.sleep(0.2)
            click_position(item_pos)
            time.sleep(0.15)
            try:
                win32api.SetCursorPos((0, 0))
            except:
                pass
            time.sleep(scan_delay_after_click)

        detected_options = scan_options(position=(row, col))
        if detected_options:
            print(f"✅ OCR 성공 ({attempt+1}번째)")
            break

    # ── 결과 처리 ──
    item_locked         = False
    item_disposed       = False
    item_dispose_failed = False
    matched_weapons     = []

    if detected_options:
        option_label.config(text=f"감지: {', '.join(detected_options)}", fg="#27ae60")
        matched_weapons = check_weapon_match(detected_options)

        if matched_weapons:
            match_label.config(text=f"✅ 일치: {', '.join(matched_weapons)}", fg="#27ae60")
            print(f"🎯 매칭: {', '.join(matched_weapons)}")

            btn = find_lock_button()
            if not btn:
                time.sleep(0.08)
                btn = find_lock_button()

            if btn:
                click_position(btn)
                scan_state["total_locked"] += 1
                item_locked = True
                print("🔐 잠금 완료")
                time.sleep(0.1)
            else:
                print("❌ 잠금 버튼 찾기 실패")
                match_label.config(text=f"✅ 일치: {', '.join(matched_weapons)} (잠금 실패)", fg="#e67e22")

        else:
            match_label.config(text="🗑️ 불일치 → 폐기", fg="#e74c3c")
            print("❌ 무기 매칭 없음 → 폐기 버튼 탐색")

            dispose_btn = find_dispose_button()
            if not dispose_btn:
                time.sleep(0.08)
                dispose_btn = find_dispose_button()

            if dispose_btn:
                click_position(dispose_btn)
                scan_state["total_disposed"] += 1
                item_disposed = True
                print("🗑️ 폐기 버튼 클릭 완료")
                time.sleep(0.1)
            else:
                print("⚠️ 폐기 버튼 찾기 실패")
                match_label.config(text="❌ 불일치 (폐기 버튼 미발견)", fg="#e74c3c")
                item_dispose_failed = True
    else:
        option_label.config(text="❌ OCR 실패 (2회)", fg="#e74c3c")
        print("❌ OCR 완전 실패")

    scan_log.append({
        'position':       (row, col),
        'status':         'scanned',
        'options':        detected_options,
        'matches':        matched_weapons,
        'locked':         item_locked,
        'disposed':       item_disposed,
        'dispose_failed': item_dispose_failed,
    })

    progress_label.config(
        text=f"진행: {scan_state['total_scanned']+1}/24 | "
             f"잠금: {scan_state['total_locked']} | "
             f"폐기: {scan_state['total_disposed']}")

    _advance_and_next(int(scan_delay_between_items * 1000))

def _advance_and_next(delay_ms):
    scan_state["total_scanned"] += 1
    scan_state["current_col"]   += 1
    if scan_state["current_col"] >= GRID_COLS:
        scan_state["current_col"]  = 0
        scan_state["current_row"] += 1
    root.after(delay_ms, scan_loop)

# ============================================================
# UI 제어
# ============================================================
def toggle_auto_scan():
    global auto_scan_enabled, scan_log

    if auto_scan_enabled:
        stop_scan_ui()
        return

    if lock_template is None or lock_button_template is None:
        status_label.config(text="❌ 잠금 템플릿 파일 필요!", fg="#e74c3c")
        return

    if dispose_button_template is None:
        print("⚠️ dispose_button_template.png 없음 - 폐기 기능 비활성화 상태로 실행")

    if not find_game_window():
        response = messagebox.askyesno("게임 창 찾기 실패",
                                       "게임 창을 찾을 수 없습니다.\n전체 화면 사용하시겠습니까?")
        if response:
            global game_window_rect, current_scale
            screen = ImageGrab.grab()
            game_window_rect = {'x': 0, 'y': 0, 'width': screen.width, 'height': screen.height}
            current_scale    = screen.width / 1280
        else:
            return

    auto_detect_option_region()
    auto_detect_grid()

    if scan_region and first_item_pos:
        scan_log = []
        init_log_file()

        total, locked, disposed = pre_scan_all_locks()

        if total == locked + disposed:
            status_label.config(text="✅ 모든 아이템 잠금/폐기 완료", fg="#2ecc71")
            messagebox.showinfo("스캔 완료",
                f"모든 아이템({total}개)이 이미 잠금({locked}) 또는 폐기({disposed}) 되어 있습니다.")
            return

        auto_scan_enabled = True
        scan_state.update({
            "current_row": 0, "current_col": 0,
            "total_scanned": 0, "total_locked": 0, "total_disposed": 0,
        })
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
        if key == keyboard.Key.f1:
            toggle_auto_scan()
        elif key == keyboard.Key.f2:
            stop_scan_ui()
    except:
        pass

keyboard.Listener(on_press=on_key_press).start()

# ============================================================
# UI 구성
# ============================================================
root = tk.Tk()
root.title("Endfield Auto Scanner")
root.geometry("600x580")
root.attributes("-topmost", True)

style = ttk.Style()
style.configure("Running.TButton", foreground="#e74c3c")

f = tk.Frame(root, padx=20, pady=20, bg="#ecf0f1")
f.pack(fill="both", expand=True)

tk.Label(f, text="엔드필드 자동 잠금/폐기 ⚡",
         font=("Malgun Gothic", 16, "bold"), bg="#ecf0f1").pack(pady=(0, 20))

auto_btn = ttk.Button(f, text="▶️ 자동 스캔 시작 (F1)", command=toggle_auto_scan)
auto_btn.pack(pady=10, fill="x")

status_label = tk.Label(f, text="⏳ 대기 중...",
                        font=("Malgun Gothic", 12, "bold"), bg="#ecf0f1", fg="#95a5a6")
status_label.pack(pady=(10, 5))

progress_label = tk.Label(f, text="진행: 0/24 | 잠금: 0 | 폐기: 0",
                          font=("Malgun Gothic", 10), bg="#ecf0f1", fg="#7f8c8d")
progress_label.pack(pady=5)

result_frame = tk.LabelFrame(f, text="📊 실시간 결과", bg="white", padx=15, pady=10,
                              font=("Malgun Gothic", 10, "bold"))
result_frame.pack(fill="both", expand=True, pady=(10, 0))

option_label = tk.Label(result_frame, text="감지: -", bg="white", anchor="w",
                        font=("Malgun Gothic", 9))
option_label.pack(fill="x", pady=3)

match_label = tk.Label(result_frame, text="매칭: -", bg="white", anchor="w",
                       font=("Malgun Gothic", 9))
match_label.pack(fill="x", pady=3)

info_label = tk.Label(result_frame,
    text="💡 옵션 불일치 시 자동으로 폐기(휴지통) 버튼 클릭",
    bg="white", anchor="w", font=("Malgun Gothic", 8), fg="#7f8c8d")
info_label.pack(fill="x", pady=(6, 0))

help_label = tk.Label(f,
    text="F1: 스캔 시작/중지  |  F2: 강제 중지\n"
         "필요 파일: lock_template / lock_button / dispose_template / dispose_button",
    bg="#ecf0f1", fg="#7f8c8d", font=("Malgun Gothic", 8))
help_label.pack(pady=(10, 0))

root.after(100, load_lock_template)
root.mainloop()
