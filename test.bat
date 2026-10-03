@echo off
if 1==1 (
    echo Running something that fails...
    cmd /c exit 1
    if %errorlevel% neq 0 (
        echo Failed inside block! Errorlevel is %errorlevel%
    ) else (
        echo Succeeded inside block? Errorlevel is %errorlevel%
    )
)
echo Outside block, Errorlevel is %errorlevel%
