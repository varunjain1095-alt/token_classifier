@echo off
echo Testing Review Classification Workbench...

REM Test backend health
echo Testing backend health...
curl -s http://localhost:8020/health
if %errorlevel% neq 0 (
    echo Backend not running!
    goto :end
)

echo.
echo Backend is healthy!

REM Test frontend proxy
echo Testing frontend proxy...
curl -s http://localhost:3000/api/health
if %errorlevel% neq 0 (
    echo Frontend proxy not working!
    goto :end
)

echo.
echo Frontend proxy is working!

REM Test session creation
echo Testing session creation...
curl -s -X POST http://localhost:3000/api/session/anonymous
if %errorlevel% neq 0 (
    echo Session creation failed!
    goto :end
)

echo.
echo Session creation working!

REM Test file upload
echo Testing file upload...
echo id,name,review_text,rating > test_upload.csv
curl -s -X POST http://localhost:3000/api/upload/file -F "file=@test_upload.csv" -b "session_id=test_session"
if %errorlevel% neq 0 (
    echo File upload failed!
    goto :end
)

echo.
echo File upload working!

echo.
echo ========================================
echo  All tests passed! System is ready.
echo ========================================

:end
pause
