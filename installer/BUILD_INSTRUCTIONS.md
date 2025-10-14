# WF Firmware Uploader - Build Instructions

## 현재 상태
✅ **실행파일(EXE)이 이미 생성되었습니다!**
- 위치: `build/dist/wf_firmware_uploader.exe`
- 크기: ~47MB
- 단일 실행파일로 모든 의존성 포함

## MSI 인스톨러 생성 방법

### 방법 1: Inno Setup 사용 (권장 - 가장 간단)

1. **Inno Setup 다운로드 및 설치**
   - https://jrsoftware.org/isdl.php
   - 무료이며 Windows에서 가장 많이 사용됨

2. **인스톨러 빌드**
   ```
   - Inno Setup을 실행
   - File > Open > build/installer.iss 선택
   - Build > Compile 클릭
   ```

3. **결과물**
   - `installer_output/WF_Firmware_Uploader_Setup_v1.0.0.exe` 생성
   - 이 EXE 파일이 설치 프로그램입니다

### 방법 2: WiX Toolset 사용 (MSI 형식)

1. **WiX Toolset 설치**
   - https://wixtoolset.org/releases/
   - WiX v3.11 이상 필요
   - PATH에 WiX bin 디렉토리 추가

2. **MSI 빌드**
   ```batch
   cd build
   build_msi.bat
   ```

3. **결과물**
   - `installer_output/WF_Firmware_Uploader_v1.0.0.msi` 생성

### 방법 3: cx_Freeze 사용 (Python 기반)

1. **cx_Freeze 설치**
   ```batch
   uv pip install cx-freeze
   ```

2. **MSI 빌드**
   ```batch
   cd build
   uv run python create_installer.py bdist_msi
   ```

3. **결과물**
   - `dist/` 폴더에 MSI 파일 생성

## 추천 방법

### 🎯 가장 빠른 방법: 실행파일만 배포
현재 `build/dist/wf_firmware_uploader.exe` 파일을 그대로 배포할 수 있습니다.
- 설치 불필요
- 단일 EXE 파일만 있으면 실행 가능
- USB나 네트워크로 쉽게 공유

### 🎯 전문적인 배포: Inno Setup
- 설치/제거 기능
- 시작 메뉴 바로가기
- 바탕화면 아이콘
- 전문적인 설치 마법사

## 파일 구조

```
build/
├── dist/
│   └── wf_firmware_uploader.exe      # 생성된 실행파일
├── installer.iss                      # Inno Setup 스크립트
├── build_msi.bat                      # WiX 빌드 스크립트
├── create_installer.py                # cx_Freeze 스크립트
└── wf_firmware_uploader.spec          # PyInstaller 설정

installer_output/                      # 인스톨러 출력 폴더 (생성됨)
└── WF_Firmware_Uploader_Setup_v1.0.0.exe
```

## 배포 옵션 비교

| 방법 | 장점 | 단점 | 파일 형식 |
|------|------|------|-----------|
| **실행파일만** | 가장 간단, 설치 불필요 | 시작 메뉴 없음 | .exe |
| **Inno Setup** | 전문적, 사용 쉬움 | 추가 도구 필요 | .exe (설치) |
| **WiX** | 표준 MSI, GPO 지원 | 복잡함 | .msi |
| **cx_Freeze** | Python 통합 | 느림 | .msi |

## 다음 단계

1. ✅ 실행파일 생성 완료
2. 📦 원하는 방법으로 인스톨러 생성 (선택사항)
3. 🧪 테스트
4. 🚀 배포

## 테스트 방법

```batch
# 실행파일 직접 실행
build\dist\wf_firmware_uploader.exe

# 또는 설치 후 시작 메뉴에서 실행
```

## 문제 해결

### 실행 시 Python 오류
- EXE는 독립 실행 가능하므로 Python 설치 불필요
- 만약 오류 발생 시 `wf_firmware_uploader.spec`에서 `console=True`로 변경 후 재빌드

### DLL 누락
- PyInstaller가 자동으로 모든 DLL 포함
- 문제 시 `.spec` 파일의 `hiddenimports`에 누락된 모듈 추가

### 바이러스 경고
- 일부 백신이 PyInstaller EXE를 오탐지할 수 있음
- VirusTotal에서 확인 후 예외 처리
- 코드 서명 인증서 사용 권장 (선택사항)
