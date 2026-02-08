import ctypes
import tkinter as tk
from tkinter import ttk
import pytesseract
from PIL import ImageGrab, ImageOps, Image, ImageEnhance, ImageFilter
import re
from pynput import keyboard
import numpy as np
import cv2

# DPI 설정 (윈도우 선명도 최적화)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    pass

# ==============================
# Tesseract 경로 설정
# ==============================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TARGET_KEYWORDS = {
    # --- 기초 속성 ---
    "main attribute": "주요 능력치",
    "agility": "민첩성", 
    "strength": "힘", 
    "will": "의지", 
    "intellect": "지능",
    
    # --- 추가 속성 ---
    "attack": "공격력", 
    "hp": "생명력",
    "treatment efficiency": "치유 효율",
    "critical rate": "치확",
    "ultimate": "궁충",
    "arts intensity": "아츠 강도", 
    "arts dmg": "아츠 피해",
    
    # --- 피해 유형 ---
    "physical": "물리 피해",
    "electric": "전기 피해",
    "heat": "열기 피해", 
    "cryo": "냉기 피해", 
    "nature": "자연 피해",
    
    # --- 스킬 속성 ---
    "assault": "강공", 
    "suppression": "억제",
    "pursuit": "추격", 
    "crusher": "분쇄", 
    "combative": "기예",
    "detonate": "방출", 
    "flow": "흐름", 
    "efficacy": "효율",
    "infliction": "고통", 
    "fracture": "골절", 
    "inspiring": "사기",
    "twilight": "어둠", 
    "medicant": "의료", 
    "brutality": "잔혹"
}

WEAPON_DB = {
        # --- 한손검 ---
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

    # --- 양손검  ---
    "분쇄의 군주★": ["힘", "치확", "분쇄"],
    "과거의 일품★": ["의지", "생명력", "효율"],
    "모범★": ["주요 능력치", "공격력", "억제"],
    "헤라펜거★": ["힘", "공격력", "방출"],
    "천둥의 흔적★": ["힘", "생명력", "의료"],
    "O.B.J. 헤비 버든": ["힘", "생명력", "효율"],
    "최후의 메아리": ["힘", "생명력", "의료"],
    "고대의 강줄기": ["힘", "아츠 강도", "잔혹"],
    "검은 추적자": ["힘", "궁충", "방출"],

    # --- 장병기  ---
    "J.E.T.★": ["주요 능력치", "공격력", "억제"],
    "용사★": ["민첩성", "물리 피해", "기예"],
    "산의 지배자★": ["민첩성", "물리 피해", "효율"],
    "중심력 ": ["의지", "전기 피해", "억제"],
    "O.B.J. 스파이크": ["의지", "물리 피해", "고통"],
    "키메라의 정의": ["힘", "궁충", "잔혹"],

    # --- 권총  ---
    "클래니벌★": ["주요 능력치", "아츠 피해", "고통"],
    "쐐기★": ["주요 능력치", "치확", "고통"],
    "예술의 폭군★": ["지능", "치확", "골절"],
    "항로의 개척자★": ["지능", "냉기 피해", "고통"],
    "이성적인 작별": ["힘", "열기 피해", "추격"],
    "O.B.J. 벨로시투스": ["민첩성", "궁충", "방출"],
    "작품: 중생": ["민첩성", "아츠 피해", "고통"],

    # --- 아츠 유닛  ---
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

target_region = None
is_running = False
guide_window = None 

class AreaSelector:
    def __init__(self, master):
        self.selections = None
        self.root = tk.Toplevel(master)
        self.root.attributes("-alpha", 0.3, "-fullscreen", True, "-topmost", True)
        self.root.config(cursor="cross")
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
        left, top = min(self.start_x, event.x), min(self.start_y, event.y)
        right, bottom = max(self.start_x, event.x), max(self.start_y, event.y)
        if (right - left) > 10:
            self.selections = (left, top, right, bottom)
        self.root.destroy()

def show_guide_rect(region):
    global guide_window
    if guide_window: guide_window.destroy()
    left, top, right, bottom = region
    guide_window = tk.Toplevel(root)
    guide_window.overrideredirect(True)
    guide_window.attributes("-topmost", True)
    guide_window.attributes("-transparentcolor", "white")
    guide_window.geometry(f"{right-left}x{bottom-top}+{left}+{top}")
    canvas = tk.Canvas(guide_window, width=right-left, height=bottom-top, bg="white", highlightthickness=0)
    canvas.pack()
    canvas.create_rectangle(0, 0, right-left, bottom-top, outline="red", width=4)

def preprocess_image_advanced(img):
    """게임 UI 전용 전처리 - 어두운 배경의 밝은 글씨"""
    
    # PIL -> OpenCV 변환
    img_array = np.array(img)
    
    # 1. 그레이스케일 변환
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    
    # 2. 리사이징 (5배 확대)
    scale = 5
    width = int(gray.shape[1] * scale)
    height = int(gray.shape[0] * scale)
    resized = cv2.resize(gray, (width, height), interpolation=cv2.INTER_CUBIC)
    
    # 3. 반전 (흰 글씨 -> 검은 글씨)
    # Tesseract는 검은 글씨를 더 잘 인식함
    inverted = cv2.bitwise_not(resized)
    
    # 4. 가우시안 블러로 노이즈 제거
    blurred = cv2.GaussianBlur(inverted, (3, 3), 0)
    
    # 5. Otsu's Binarization (자동 임계값)
    # 배경과 텍스트를 자동으로 분리
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 6. 대비 강화
    binary = cv2.convertScaleAbs(binary, alpha=1.3, beta=10)
    
    # 7. 다시 한번 이진화 (노이즈 완전 제거)
    _, final = cv2.threshold(binary, 200, 255, cv2.THRESH_BINARY)
    
    # 8. 모폴로지 연산 (작은 노이즈 제거)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    final = cv2.morphologyEx(final, cv2.MORPH_OPEN, kernel, iterations=1)
    final = cv2.morphologyEx(final, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # 9. 테두리 추가 (OCR 정확도 향상)
    final = cv2.copyMakeBorder(final, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    
    # OpenCV -> PIL 변환
    result = Image.fromarray(final)
    
    return result

def update_loop():
    global is_running, target_region
    if not is_running or target_region is None: return

    try:
        # 1. 원본 캡처
        img = ImageGrab.grab(bbox=target_region)
        
        # 2. 고급 전처리 적용
        processed_img = preprocess_image_advanced(img)
        
        # [디버그용] 전처리된 이미지 저장
        processed_img.save("debug_processed.png")
        
        # 3. OCR 실행
        # PSM 7: 단일 텍스트 라인으로 처리
        custom_config = r'--oem 3 --psm 7'
        text1 = pytesseract.image_to_string(processed_img, lang="eng", config=custom_config)
        
        # PSM 6: 단일 균일 텍스트 블록
        custom_config2 = r'--oem 3 --psm 6'
        text2 = pytesseract.image_to_string(processed_img, lang="eng", config=custom_config2)
        
        # PSM 13: 원시 라인 (Raw line)
        custom_config3 = r'--oem 3 --psm 13'
        text3 = pytesseract.image_to_string(processed_img, lang="eng", config=custom_config3)
        
        # 세 결과 합치기
        combined_text = f"{text1} {text2} {text3}"
        
        # 4. 텍스트 정제 및 오타 보정
        clean_text = re.sub(r'[^a-zA-Z\s]', ' ', combined_text).lower()
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # 오타 보정 매핑 (OCR이 자주 헷갈리는 문자들)
        typo_fixes = {
            'atlribute': 'attribute',
            'altribute': 'attribute',
            'atribute': 'attribute',
            'attribut': 'attribute',
            'attributee': 'attribute',  # 추가
            'boast': 'boost',
            'bcost': 'boost',
            'boosl': 'boost',
            'criticai': 'critical',
            'critica': 'critical',
            'criticall': 'critical',  # 추가
            'crilical': 'critical',
            'rale': 'rate',
            'rafe': 'rate',
            'infliction': 'infliction',
            'infiiction': 'infliction',
            'maln': 'main',
            'maim': 'main',
            'mam': 'main'
        }
        
        for typo, correct in typo_fixes.items():
            clean_text = clean_text.replace(typo, correct)
        
        print(f"[DEBUG] 원본: {combined_text[:150]}")
        print(f"[DEBUG] 정제: {clean_text}")
        
        found_kor, found_eng = [], []
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
                        found_eng.append(eng.title())
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
                        found_eng.append(eng.title())
                        found_kor.append(kor)
                        found_raw.append(eng)
        
        # UI 업데이트
        result_label.config(
            text="\n".join(found_eng) if found_eng else "감지 중...",
            fg="#27ae60" if found_eng else "#95a5a6"
        )
        
        print(f"[DEBUG] 감지된 한국어: {found_kor}")
        
        # 무기 매칭
        matches = []
        if found_kor:
            for name, opts in WEAPON_DB.items():
                if all(o in found_kor for o in opts):
                    matches.append(name)
                    print(f"[DEBUG] ✅ {name} 매칭!")
        
        print(f"[DEBUG] 최종 매칭 리스트: {matches}")
        
        # UI 업데이트 (강제 리프레시)
        if matches:
            match_text = "✅ 일치:\n" + "\n".join(matches)
            match_label.config(
                text=match_text, 
                fg="#27ae60",  # 초록색
                bg="white"
            )
        else:
            match_label.config(
                text="🔍 일치 없음", 
                fg="#95a5a6",  # 회색
                bg="white"
            )
        
        # 강제 UI 업데이트
        root.update_idletasks()
                            
    except Exception as e:
        print(f"OCR Error: {e}")
        import traceback
        traceback.print_exc()
        
    root.after(400, update_loop)

def start_scan():
    global is_running, target_region
    if is_running: return
    selector = AreaSelector(root)
    root.wait_window(selector.root)
    if selector.selections:
        target_region = selector.selections
        is_running = True
        show_guide_rect(target_region)
        btn_start.config(text="■ 중지 (F2)", style="Stop.TButton")
        update_loop()

def stop_scan():
    global is_running, guide_window
    is_running = False
    if guide_window:
        guide_window.destroy()
        guide_window = None
    btn_start.config(text="▶ 시작 (F1)", style="TButton")
    match_label.config(text="중지됨", fg="#c0392b", bg="white")

def on_press_key(key):
    try:
        if key == keyboard.Key.f1: start_scan()
        elif key == keyboard.Key.f2: stop_scan()
    except: pass

listener = keyboard.Listener(on_press=on_press_key)
listener.start()

root = tk.Tk()
root.title("Endfield Scanner Pro - Enhanced OCR")
root.geometry("500x800")
root.attributes("-topmost", True)

style = ttk.Style()
style.configure("Stop.TButton", foreground="red", font=("Malgun Gothic", 10, "bold"))

f = tk.Frame(root, padx=20, pady=20, bg="#ecf0f1")
f.pack(fill="both", expand=True)

tk.Label(f, text="실시간 정밀 스캐너 Pro", font=("Malgun Gothic", 16, "bold"), bg="#ecf0f1").pack(pady=10)
tk.Label(f, text="[ F1: 시작 | F2: 중지 ]", fg="#3498db", font=("Malgun Gothic", 10), bg="#ecf0f1").pack()
tk.Label(f, text="💡 Tip: 각 옵션 항목을 개별적으로 드래그하세요", fg="#e74c3c", font=("Malgun Gothic", 9), bg="#ecf0f1").pack(pady=5)

btn_start = ttk.Button(f, text="▶ 시작 (F1)", command=start_scan)
btn_start.pack(pady=15, fill="x")

tk.Label(f, text="감지된 옵션 (OCR):", font=("Malgun Gothic", 10, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(10,5))
result_label = tk.Label(f, text="-", font=("Consolas", 11), bg="white", height=6, width=45, relief="solid", anchor="nw", justify="left", padx=10, pady=10)
result_label.pack(pady=5)

tk.Label(f, text="일치하는 무기:", font=("Malgun Gothic", 10, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(10,5))

# 매칭 결과용 별도 프레임 (흰색 배경)
match_frame = tk.Frame(f, bg="white", relief="solid", borderwidth=1)
match_frame.pack(fill="both", expand=True, pady=5)

match_label = tk.Label(
    match_frame, 
    text="F1을 눌러 영역을 드래그하세요", 
    font=("Malgun Gothic", 12, "bold"), 
    bg="white",  # 흰 배경
    fg="#2c3e50",  # 진한 회색 텍스트
    wraplength=440,
    justify="left",
    anchor="nw",
    padx=10,
    pady=10
)
match_label.pack(fill="both", expand=True)

root.mainloop()
