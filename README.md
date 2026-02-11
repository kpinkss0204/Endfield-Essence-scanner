# Endfield Auto Scanner

엔드필드 무기 옵션을 자동으로 인식하고 원하는 조합을 잠금하는 도구

## 주요 기능

- 🔍 **자동 OCR**: 무기 옵션을 한국어로 자동 인식
- 🎯 **스마트 매칭**: weapons_db.json 기반 원하는 옵션 조합 자동 탐지
- 🔒 **자동 잠금**: 매칭된 무기를 자동으로 잠금
- ⌨️ **단축키 제어**: F1(시작/중지), F2(강제 중지)

## 필수 요구사항

- **Tesseract OCR** 설치 필수
  - 다운로드: https://github.com/UB-Mannheim/tesseract/wiki
  - 설치 경로: `C:\Program Files\Tesseract-OCR\`
  - 한국어 언어팩(kor.traineddata) 포함 설치

## 설치 및 실행

### 방법 1: EXE 파일 (권장)
1. `EndField_Auto_Scanner.exe` 다운로드
2. 같은 폴더에 다음 파일 배치:
   - `weapons_db.json`
   - `lock_template.png`
   - `lock_button_template.png`
3. exe 파일 실행

### 방법 2: Python 소스코드
```bash
pip install -r requirements.txt
python endfield_essence_scanner.py
```

## 사용 방법

1. 엔드필드 게임 실행 및 인벤토리 열기
2. 스캐너 실행
3. **F1** 키 또는 "자동 스캔 시작" 버튼 클릭
4. 자동으로 아이템 스캔 및 잠금 진행

## 설정

`weapons_db.json` 파일을 수정하여 원하는 무기 옵션 조합 설정:
```json
{
  "무기이름": ["주요 능력치", "공격력", "억제"],
  "다른무기": ["생명력", "민첩성", "강공"]
}
```

## 단축키

- **F1**: 스캔 시작/중지
- **F2**: 강제 중지

## 지원 해상도

- 1280x768 (기본)
- 1920x1080
- 1600x900
- 2560x1440
- 1366x768

다른 해상도는 자동 스케일링 적용

## 문제 해결

### 템플릿 파일 오류
→ `lock_template.png`, `lock_button_template.png` 파일이 exe와 같은 폴더에 있는지 확인

### OCR 인식 실패
→ Tesseract 설치 및 한국어 언어팩 확인

### 게임 창 인식 실패
→ 게임 창 제목에 "Endfield", "엔드필드", "明日方舟" 포함되어 있는지 확인

## 라이선스

MIT License