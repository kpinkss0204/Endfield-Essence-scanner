import ctypes
import tkinter as tk
from tkinter import ttk
import pytesseract
from PIL import ImageGrab, Image
import re
from pynput import keyboard
import numpy as np
import cv2
import time
import win32api
import win32con
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
item_spacing = None
lock_button_pos = None
lock_template = None  # 템플릿 이미지
lock_button_template = None  # 잠금 버튼 템플릿

GRID_COLS = 4
GRID_ROWS = 5

auto_scan_enabled = False
scan_state = {"current_row": 0, "current_col": 0, "total_scanned": 0, "total_locked": 0}

def click_position(pos):
    if not pos: return False
    x, y = pos
    try:
        win32api.SetCursorPos((x, y))
        time.sleep(0.02)  # 50ms → 20ms
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.02)  # 50ms → 20ms
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        return True
    except: return False

def detect_yellow_items():
    """현재 화면에서 노란색 등급바가 있는 아이템 위치들을 모두 찾음"""
    try:
        screen = np.array(ImageGrab.grab())
        hsv = cv2.cvtColor(screen, cv2.COLOR_RGB2HSV)

        # 노란색 HSV 범위
        lower_yellow = np.array([15, 150, 150])
        upper_yellow = np.array([35, 255, 255])

        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detected_points = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 40 and h < 15:  # 가로로 긴 형태 필터링
                item_center = (x + w//2, y - 60)  # 아이템 중심점으로 보정
                detected_points.append(item_center)

        return detected_points
    except:
        return []

def is_item_at_position(target_pos, tolerance=50):
    """특정 위치에 아이템(노란색 바)이 실제로 존재하는지 확인"""
    detected_items = detect_yellow_items()
    
    for item_pos in detected_items:
        # 오차 범위 내에 있으면 아이템이 존재한다고 판단
        if abs(item_pos[0] - target_pos[0]) < tolerance and abs(item_pos[1] - target_pos[1]) < tolerance:
            return True
    return False

def load_lock_template():
    """저장된 잠금 템플릿 불러오기 (고정 파일 사용)"""
    global lock_template, lock_button_template
    
    # 잠금 아이콘 템플릿 로드
    if os.path.exists("lock_template.png"):
        lock_template = cv2.imread("lock_template.png", cv2.IMREAD_GRAYSCALE)
        print(f"[INFO] 잠금 아이콘 템플릿 로드 성공: {lock_template.shape}")
    else:
        print("[ERROR] lock_template.png 파일이 없습니다!")
    
    # 잠금 버튼 템플릿 로드
    if os.path.exists("lock_button_template.png"):
        lock_button_template = cv2.imread("lock_button_template.png", cv2.IMREAD_GRAYSCALE)
        print(f"[INFO] 잠금 버튼 템플릿 로드 성공: {lock_button_template.shape}")
    else:
        print("[ERROR] lock_button_template.png 파일이 없습니다!")
    
    # UI 업데이트
    if lock_template is not None:
        template_label.config(text="✅ 아이콘 템플릿 로드 완료", fg="#27ae60")
    else:
        template_label.config(text="❌ lock_template.png 없음", fg="#e74c3c")
    
    if lock_button_template is not None:
        lock_btn_label.config(text="✅ 버튼 템플릿 로드 완료", fg="#27ae60")
    else:
        lock_btn_label.config(text="❌ lock_button_template.png 없음", fg="#e74c3c")

def find_lock_button():
    """화면에서 잠금 버튼 템플릿을 찾아 위치 반환"""
    global lock_button_template
    
    if lock_button_template is None:
        print("[WARNING] 잠금 버튼 템플릿이 없습니다.")
        return None
    
    try:
        # 화면 전체 캡처 (옵션 창 영역만)
        # 옵션 창은 보통 화면 중앙 우측에 있으므로 우측 절반만 검색
        screen = ImageGrab.grab()
        screen_width = screen.width
        search_bbox = (screen_width // 2, 0, screen_width, screen.height)
        search_img = ImageGrab.grab(bbox=search_bbox)
        search_gray = cv2.cvtColor(np.array(search_img), cv2.COLOR_RGB2GRAY)
        
        # 템플릿 매칭
        result = cv2.matchTemplate(search_gray, lock_button_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= 0.7:  # 70% 이상 일치
            # 버튼 중심 좌표 계산 (화면 전체 기준)
            h, w = lock_button_template.shape
            button_x = search_bbox[0] + max_loc[0] + w // 2
            button_y = max_loc[1] + h // 2
            
            print(f"[INFO] 잠금 버튼 발견: ({button_x}, {button_y}), 점수: {max_val:.3f}")
            return (button_x, button_y)
        else:
            print(f"[WARNING] 잠금 버튼을 찾지 못했습니다 (점수: {max_val:.3f})")
            return None
            
    except Exception as e:
        print(f"[ERROR] 잠금 버튼 찾기 실패: {e}")
        return None

def is_item_locked_template(item_pos):
    """템플릿 매칭으로 잠금 아이콘 감지"""
    global lock_template
    
    if lock_template is None:
        print("[WARNING] 템플릿이 없습니다.")
        return False
    
    try:
        # 아이템 위치 왼쪽 아래에서 넓은 영역 캡처
        check_x = item_pos[0] - 60
        check_y = item_pos[1] + 20
        
        # 검색 영역 (60x60 픽셀로 넓게)
        search_bbox = (check_x, check_y, check_x + 60, check_y + 60)
        search_img = ImageGrab.grab(bbox=search_bbox)
        search_gray = cv2.cvtColor(np.array(search_img), cv2.COLOR_RGB2GRAY)
        
        # 템플릿 매칭
        result = cv2.matchTemplate(search_gray, lock_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        # 유사도 0.6 이상이면 잠금으로 판단
        if max_val >= 0.6:
            print(f"[INFO] 잠금 감지됨! (점수: {max_val:.3f})")
            return True
        
        return False
        
    except Exception as e:
        print(f"[WARNING] 템플릿 매칭 실패: {e}")
        return False

def auto_detect_option_region():
    """옵션 창의 노란색 막대를 감지하여 영역을 자동으로 설정"""
    global scan_region
    
    try:
        status_label.config(text="🔍 옵션 영역 찾는 중 (노란색 막대 감지)...", fg="#f39c12")
        root.update()
        
        # 화면 전체 캡처
        screen = np.array(ImageGrab.grab())
        height, width = screen.shape[:2]
        
        # HSV로 변환
        hsv = cv2.cvtColor(screen, cv2.COLOR_RGB2HSV)
        
        # 밝은 노란색 범위 (옵션 왼쪽의 노란색 막대)
        lower_yellow = np.array([20, 100, 150])
        upper_yellow = np.array([35, 255, 255])
        
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # 컨투어 찾기
        contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 세로로 긴 노란색 막대 찾기
        yellow_bars = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # 세로가 가로보다 길고, 작은 막대 형태
            if h > w and h > 30 and w < 20:
                yellow_bars.append((x, y, w, h))
                print(f"[DEBUG] 노란 막대 발견: x={x}, y={y}, w={w}, h={h}")
        
        print(f"[DEBUG] 총 {len(yellow_bars)}개의 노란 막대 발견")
        
        if len(yellow_bars) < 3:
            status_label.config(
                text=f"❌ 옵션 노란 막대를 찾을 수 없습니다! ({len(yellow_bars)}개 발견, 3개 필요)\n아이템을 클릭하여 옵션 창을 여세요!", 
                fg="#e74c3c"
            )
            return
        
        # Y좌표로 정렬하여 연속된 3개 찾기
        yellow_bars.sort(key=lambda b: b[1])
        
        # 가까이 있는 3개 막대 찾기 (옵션은 연속으로 배치됨)
        for i in range(len(yellow_bars) - 2):
            bar1, bar2, bar3 = yellow_bars[i], yellow_bars[i+1], yellow_bars[i+2]
            
            # 세 막대가 비슷한 간격으로 있는지 확인
            gap1 = bar2[1] - (bar1[1] + bar1[3])
            gap2 = bar3[1] - (bar2[1] + bar2[3])
            
            # 간격이 비슷하면 (오차 30px 이내)
            if abs(gap1 - gap2) < 30 and gap1 < 100:
                # 3개 막대를 포함하는 영역 계산 (좌우 폭 축소)
                min_x = min(bar1[0], bar2[0], bar3[0]) + 15  # 왼쪽 여백 줄임
                min_y = bar1[1]  # 위쪽 여백 10px 줄임
                max_x = max(bar1[0] + bar1[2], bar2[0] + bar2[2], bar3[0] + bar3[2]) + 240  # 오른쪽 폭 축소
                max_y = bar3[1] + bar3[3]  # 아래쪽 여백 10px 줄임
                
                scan_region = (min_x, min_y, max_x, max_y)
                
                # 감지된 영역을 화면에 표시
                show_detected_region(screen, scan_region, yellow_bars[i:i+3])
                
                scan_region_label.config(
                    text=f"✅ 옵션 영역: ({min_x},{min_y}) ~ ({max_x},{max_y})",
                    fg="#27ae60"
                )
                status_label.config(text="👍 옵션 영역 자동 설정 완료!", fg="#2ecc71")
                print(f"[INFO] 옵션 영역 자동 감지: {scan_region}")
                return
        
        # 연속된 3개를 못 찾았으면 첫 3개 사용
        top_3 = yellow_bars[:3]
        min_x = min(b[0] for b in top_3) + 15  # 왼쪽 여백 줄임
        min_y = min(b[1] for b in top_3)  # 위쪽 여백 10px 줄임
        max_x = max(b[0] + b[2] for b in top_3) + 240  # 오른쪽 폭 축소
        max_y = max(b[1] + b[3] for b in top_3)  # 아래쪽 여백 10px 줄임
        
        scan_region = (min_x, min_y, max_x, max_y)
        
        # 감지된 영역을 화면에 표시
        show_detected_region(screen, scan_region, top_3)
        
        scan_region_label.config(
            text=f"✅ 옵션 영역: ({min_x},{min_y}) ~ ({max_x},{max_y})",
            fg="#27ae60"
        )
        status_label.config(text="👍 옵션 영역 자동 설정 완료!", fg="#2ecc71")
        print(f"[INFO] 옵션 영역 자동 감지: {scan_region}")
        
    except Exception as e:
        status_label.config(text=f"❌ 옵션 영역 감지 실패: {str(e)}", fg="#e74c3c")
        print(f"[ERROR] 옵션 영역 감지 오류: {e}")
        import traceback
        traceback.print_exc()

def show_detected_region(screen, region, yellow_bars):
    """감지된 옵션 영역을 빨간 사각형으로 표시하여 저장"""
    try:
        # 디버그 이미지 저장 생략 (불필요)
        print(f"[INFO] 옵션 영역 감지 완료: {region}")
        
    except Exception as e:
        print(f"[ERROR] 영역 표시 실패: {e}")

def auto_detect_grid():
    """노란색 등급바를 감지하여 그리드 좌표 자동 설정"""
    try:
        status_label.config(text="🔍 화면에서 노란색 바 찾는 중...", fg="#f39c12")
        root.update()
        
        detected_points = detect_yellow_items()

        if len(detected_points) < 2:
            status_label.config(text="❌ 노란색 아이템이 부족합니다! (최소 2개 필요)", fg="#e74c3c")
            return

        detected_points.sort(key=lambda p: (p[1], p[0]))  # Y우선 정렬

        global first_item_pos, item_spacing
        first_item_pos = detected_points[0]

        # 가로 간격 계산
        spacing_x = detected_points[1][0] - detected_points[0][0]
        
        # 세로 간격 계산
        spacing_y = 0
        for p in detected_points:
            if p[1] > first_item_pos[1] + 50:
                spacing_y = p[1] - first_item_pos[1]
                break
        
        if spacing_y == 0: 
            spacing_y = spacing_x

        item_spacing = (spacing_x, spacing_y)
        
        auto_setup_label.config(text=f"✅ 감지: ({first_item_pos[0]},{first_item_pos[1]})", fg="#27ae60")
        spacing_label.config(text=f"✅ 간격: 가로={spacing_x}px, 세로={spacing_y}px", fg="#27ae60")
        status_label.config(text=f"👍 자동 설정 완료! ({len(detected_points)}개 발견)", fg="#2ecc71")
        
    except Exception as e:
        status_label.config(text=f"❌ 오류: {str(e)}", fg="#e74c3c")

class AreaSelector:
    def __init__(self, master):
        self.selections = None
        self.root = tk.Toplevel(master)
        self.root.attributes("-alpha", 0.3, "-fullscreen", True, "-topmost", True)
        self.canvas = tk.Canvas(self.root, bg="gray")
        self.canvas.pack(fill="both", expand=True)
        self.start_x = self.start_y = 0
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        left, top, right, bottom = min(self.start_x, event.x), min(self.start_y, event.y), max(self.start_x, event.x), max(self.start_y, event.y)
        if (right - left) > 10: self.selections = (left, top, right, bottom)
        self.root.destroy()

class PointSelector:
    def __init__(self, master):
        self.position = None
        self.root = tk.Toplevel(master)
        self.root.attributes("-alpha", 0.3, "-fullscreen", True, "-topmost", True)
        self.canvas = tk.Canvas(self.root, bg="gray")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        self.position = (event.x, event.y)
        self.root.destroy()

def set_scan_region():
    global scan_region
    selector = AreaSelector(root)
    root.wait_window(selector.root)
    if selector.selections:
        scan_region = selector.selections
        scan_region_label.config(text="옵션 영역: 설정 완료 ✓", fg="#27ae60")

def set_lock_button():
    global lock_button_pos
    selector = PointSelector(root)
    root.wait_window(selector.root)
    if selector.position:
        lock_button_pos = selector.position
        lock_btn_label.config(text=f"잠금 버튼: ({lock_button_pos[0]}, {lock_button_pos[1]}) ✓", fg="#27ae60")

def get_item_position(row, col):
    if not first_item_pos or not item_spacing: return None
    return (first_item_pos[0] + (col * item_spacing[0]), first_item_pos[1] + (row * item_spacing[1]))

def preprocess_image_advanced(img):
    """게임 UI 전용 전처리 - 속도 최적화 버전"""
    
    # PIL -> OpenCV 변환
    img_array = np.array(img)
    
    # 1. 그레이스케일 변환
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    
    # 2. 리사이징 (3배 확대 - 속도 향상, 5배→3배)
    scale = 3
    width = int(gray.shape[1] * scale)
    height = int(gray.shape[0] * scale)
    resized = cv2.resize(gray, (width, height), interpolation=cv2.INTER_LINEAR)  # CUBIC→LINEAR (더 빠름)
    
    # 3. 반전 (흰 글씨 -> 검은 글씨)
    inverted = cv2.bitwise_not(resized)
    
    # 4. Otsu's Binarization (자동 임계값)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 5. 대비 강화 (간소화)
    binary = cv2.convertScaleAbs(binary, alpha=1.2, beta=5)
    
    # 6. 테두리 추가 (OCR 정확도 향상)
    final = cv2.copyMakeBorder(binary, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    
    # OpenCV -> PIL 변환
    result = Image.fromarray(final)
    
    return result

def scan_options():
    try:
        # 옵션 영역 캡처
        img = ImageGrab.grab(bbox=scan_region)
        
        # 전처리
        processed_img = preprocess_image_advanced(img)
        
        # OCR 실행 (2개 모드만 사용 - 속도 향상)
        custom_config = r'--oem 3 --psm 7'
        text1 = pytesseract.image_to_string(processed_img, lang="eng", config=custom_config)
        
        custom_config2 = r'--oem 3 --psm 6'
        text2 = pytesseract.image_to_string(processed_img, lang="eng", config=custom_config2)
        
        # 두 결과 합치기
        combined_text = f"{text1} {text2}"
        
        # 텍스트 정제
        clean_text = re.sub(r'[^a-zA-Z\s]', ' ', combined_text).lower()
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # 오타 보정
        typo_fixes = {
            'atlribute': 'attribute', 'altribute': 'attribute', 'atribute': 'attribute',
            'attribut': 'attribute', 'attributee': 'attribute',
            'boast': 'boost', 'bcost': 'boost', 'boosl': 'boost',
            'criticai': 'critical', 'critica': 'critical', 'criticall': 'critical', 'crilical': 'critical',
            'rale': 'rate', 'rafe': 'rate',
            'infliction': 'infliction', 'infiiction': 'infliction',
            'maln': 'main', 'maim': 'main', 'mam': 'main'
        }
        
        for typo, correct in typo_fixes.items():
            clean_text = clean_text.replace(typo, correct)
        
        found_kor = []
        found_raw = []  # 중복 방지용
        
        # 복합 키워드 먼저 검사 (긴 것부터)
        sorted_keys = sorted(TARGET_KEYWORDS.keys(), key=len, reverse=True)
        
        for eng in sorted_keys:
            # 이미 찾은 키워드는 건너뛰기
            if eng in found_raw:
                continue
                
            # 공백 포함 키워드는 정확히 찾기
            if ' ' in eng:
                if eng in clean_text:
                    kor = TARGET_KEYWORDS[eng]
                    if kor not in found_kor:
                        found_kor.append(kor)
                        found_raw.append(eng)
                        # 복합 키워드를 찾았으면 구성 단어들은 제외
                        for word in eng.split():
                            found_raw.append(word)
            else:
                # 단일 단어는 단어 경계로 찾기
                pattern = r'\b' + re.escape(eng) + r'\b'
                if re.search(pattern, clean_text):
                    kor = TARGET_KEYWORDS[eng]
                    if kor not in found_kor:
                        found_kor.append(kor)
                        found_raw.append(eng)
        
        return found_kor
        
    except Exception as e:
        print(f"[ERROR] 스캔 실패: {e}")
        return []

def check_weapon_match(options):
    return [name for name, req in WEAPON_DB.items() if all(opt in options for opt in req)]

def scan_loop():
    global auto_scan_enabled, scan_state
    if not auto_scan_enabled: return
    
    row, col = scan_state["current_row"], scan_state["current_col"]
    
    # 전체 그리드 스캔 완료
    if row >= GRID_ROWS:
        status_label.config(text=f"✅ 완료! (총 {scan_state['total_scanned']}개, 잠금 {scan_state['total_locked']}개)", fg="#2ecc71")
        stop_scan_ui()
        return

    item_pos = get_item_position(row, col)
    
    # 🔥 핵심: 해당 위치에 아이템이 실제로 존재하는지 확인
    if not is_item_at_position(item_pos):
        print(f"[INFO] [{row},{col}] 위치에 아이템 없음 → 스캔 종료")
        status_label.config(
            text=f"✅ 스캔 완료! (아이템 {scan_state['total_scanned']}개, 잠금 {scan_state['total_locked']}개)", 
            fg="#2ecc71"
        )
        stop_scan_ui()
        return
    
    # 아이템이 존재하면 클릭 및 스캔 진행
    print(f"[INFO] [{row},{col}] 아이템 발견, 스캔 시작")
    status_label.config(text=f"🖱️ [{row},{col}] 클릭 중...", fg="#3498db")
    click_position(item_pos)
    time.sleep(0.3)  # 600ms → 300ms (옵션창 로딩 대기)
    
    # 🔒 템플릿 매칭으로 잠금 여부 확인
    if is_item_locked_template(item_pos):
        print(f"[INFO] [{row},{col}] 이미 잠금됨, 건너뜀")
        status_label.config(text=f"🔒 [{row},{col}] 이미 잠금됨", fg="#95a5a6")
        match_label.config(text="🔒 이미 잠금된 아이템", fg="#95a5a6")
        
        # 다음 아이템으로 이동
        scan_state["current_col"] += 1
        if scan_state["current_col"] >= GRID_COLS:
            scan_state["current_col"] = 0
            scan_state["current_row"] += 1
        
        progress_label.config(text=f"진행: {scan_state['total_scanned']}/20 | 잠금: {scan_state['total_locked']}")
        root.after(250, scan_loop)  # 400ms → 250ms (잠금 아이템은 더 빠르게)
        return
    
    detected_options = scan_options()
    if detected_options:
        option_label.config(text="감지: " + ", ".join(detected_options), fg="#27ae60")
        matches = check_weapon_match(detected_options)
        if matches:
            match_label.config(text="✅ 일치: " + ", ".join(matches), fg="#27ae60")
            
            # 잠금 버튼 위치 찾기 (템플릿 매칭 사용)
            button_pos = find_lock_button()
            if button_pos:
                click_position(button_pos)
                scan_state["total_locked"] += 1
                time.sleep(0.15)  # 300ms → 150ms
            else:
                print(f"[WARNING] 잠금 버튼을 찾을 수 없어 잠금 건너뜀")
        else:
            match_label.config(text="❌ 일치 없음", fg="#95a5a6")
    else:
        option_label.config(text="감지: 실패", fg="#e74c3c")
    
    scan_state["total_scanned"] += 1
    scan_state["current_col"] += 1
    if scan_state["current_col"] >= GRID_COLS:
        scan_state["current_col"] = 0
        scan_state["current_row"] += 1
    
    progress_label.config(text=f"진행: {scan_state['total_scanned']}/20 | 잠금: {scan_state['total_locked']}")
    root.after(400, scan_loop)  # 800ms → 400ms (전체 루프 속도 2배 향상!)

def toggle_auto_scan():
    global auto_scan_enabled
    
    if auto_scan_enabled:
        # 이미 실행 중이면 중지
        stop_scan_ui()
        return
    
    # 템플릿 로드 확인
    if lock_template is None or lock_button_template is None:
        status_label.config(text="❌ 템플릿 파일이 없습니다! (lock_template.png, lock_button_template.png)", fg="#e74c3c")
        return
    
    status_label.config(text="🔍 자동 설정 시작...", fg="#f39c12")
    root.update()
    
    # 1. 옵션 영역 자동 감지
    auto_detect_option_region()
    time.sleep(0.2)  # 500ms → 200ms
    
    if scan_region is None:
        status_label.config(text="❌ 옵션 영역을 찾을 수 없습니다! 아이템을 클릭하세요!", fg="#e74c3c")
        return
    
    # 2. 그리드 자동 감지
    auto_detect_grid()
    time.sleep(0.2)  # 500ms → 200ms
    
    if first_item_pos is None or item_spacing is None:
        status_label.config(text="❌ 그리드를 찾을 수 없습니다! 노란색 아이템이 화면에 있는지 확인하세요!", fg="#e74c3c")
        return
    
    # 3. 스캔 시작
    auto_scan_enabled = True
    scan_state.update({"current_row": 0, "current_col": 0, "total_scanned": 0, "total_locked": 0})
    auto_btn.config(text="⏸️ 스캔 중지 (F1/F2)", style="Running.TButton")
    status_label.config(text="🚀 스캔 중...", fg="#2ecc71")
    scan_loop()

def stop_scan_ui():
    """스캔 즉시 중단 및 UI 초기화"""
    global auto_scan_enabled
    auto_scan_enabled = False
    auto_btn.config(text="▶️ 자동 스캔 시작 (F1)", style="TButton")
    status_label.config(text="⏹️ 중단됨 (F2)", fg="#e74c3c")

def on_key_press(key):
    try:
        if key == keyboard.Key.f1: toggle_auto_scan()
        elif key == keyboard.Key.f2: stop_scan_ui()
    except: pass

keyboard.Listener(on_press=on_key_press).start()

# UI 구성
root = tk.Tk()
root.title("Endfield Auto Scanner v4.0 - F1로 즉시 시작")
root.geometry("500x750")
root.attributes("-topmost", True)

style = ttk.Style()
style.configure("Running.TButton", foreground="#e74c3c")

f = tk.Frame(root, padx=20, pady=20, bg="#ecf0f1")
f.pack(fill="both", expand=True)

tk.Label(f, text="엔드필드 자동 잠금 시스템", font=("Malgun Gothic", 16, "bold"), bg="#ecf0f1").pack(pady=10)
tk.Label(f, text="✨ F1 누르면 바로 시작!", font=("Malgun Gothic", 11, "bold"), fg="#e67e22", bg="#ecf0f1").pack()

setup_frame = tk.LabelFrame(f, text="📊 상태", bg="white", padx=10, pady=10)
setup_frame.pack(fill="x", pady=10)

template_label = tk.Label(setup_frame, text="템플릿 로딩 중...", bg="white", fg="#95a5a6")
template_label.pack(anchor="w")
lock_btn_label = tk.Label(setup_frame, text="버튼 템플릿 로딩 중...", bg="white", fg="#95a5a6")
lock_btn_label.pack(anchor="w")
scan_region_label = tk.Label(setup_frame, text="옵션 영역: 자동 감지 대기", bg="white", fg="#95a5a6")
scan_region_label.pack(anchor="w")
auto_setup_label = tk.Label(setup_frame, text="그리드: 자동 감지 대기", bg="white", fg="#95a5a6")
auto_setup_label.pack(anchor="w")
spacing_label = tk.Label(setup_frame, text="", bg="white", fg="#95a5a6")
spacing_label.pack(anchor="w")

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

tk.Label(f, text="💡 사용법\n1. lock_template.png, lock_button_template.png 파일 준비\n2. 아이템 클릭하여 옵션 창 열기\n3. F1 누르면 자동 스캔 시작!", 
         font=("Malgun Gothic", 9), fg="#3498db", bg="#ecf0f1").pack(pady=5)
tk.Label(f, text="🔑 단축키: F1 (시작/중지) | F2 (강제 중지)", font=("Malgun Gothic", 10, "bold"), fg="#e67e22", bg="#ecf0f1").pack(pady=5)

# 시작 시 자동 템플릿 로드 시도
root.after(100, load_lock_template)

root.mainloop()
