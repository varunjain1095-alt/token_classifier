@echo off
echo Starting Review Classification Workbench...

REM Kill any existing processes
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start backend
echo Starting backend on port 8020...
start "Backend" cmd /k "cd /d C:\Projects\Scraper token review and classification review project && uvicorn src.api.main:app --host 0.0.0.0 --port 8020 --reload"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend
echo Starting frontend on port 3000...
start "Frontend" cmd /k "cd /d C:\Projects\Scraper token review and classification review project\frontend && npm run dev"

REM Wait for frontend to start
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo  Review Classification Workbench Ready!
echo ========================================
echo  Backend:  http://localhost:8020
echo  Frontend: http://localhost:3000
echo  API Docs: http://localhost:8020/docs
echo ========================================
echo.
pause
