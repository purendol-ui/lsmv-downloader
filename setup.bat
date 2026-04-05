@echo off
REM ============================================================
REM  LSMV 다운로더 - 환경 설정 스크립트 (Windows)
REM  처음 한 번만 실행하면 됩니다.
REM ============================================================

echo.
echo [1/4] Python 가상환경(venv) 생성 중...
python -m venv venv
if errorlevel 1 (
    echo ❌ 가상환경 생성 실패. Python이 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)
echo ✅ 가상환경 생성 완료

echo.
echo [2/4] 가상환경 활성화...
call venv\Scripts\activate.bat

echo.
echo [3/4] 패키지 설치 중 (playwright)...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 패키지 설치 실패
    pause
    exit /b 1
)
echo ✅ 패키지 설치 완료

echo.
echo [4/4] Playwright 브라우저(Chromium) 설치 중...
playwright install chromium
if errorlevel 1 (
    echo ❌ Playwright 브라우저 설치 실패
    pause
    exit /b 1
)
echo ✅ 브라우저 설치 완료

echo.
echo ============================================================
echo  환경 설정이 완료되었습니다!
echo  이 VS Code에서 F5를 눌러 실행하거나,
echo  아래 명령어로 직접 실행할 수 있습니다:
echo.
echo    venv\Scripts\activate
echo    python lsmv_downloader.py
echo ============================================================
echo.
pause
