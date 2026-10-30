@echo off
setlocal
title Street Lighting - road lighting design
cd /d "%~dp0"
set "LOG=%~dp0startup_log.txt"
echo ============================================================ > "%LOG%"
echo Street Lighting launcher   %DATE% %TIME%                     >> "%LOG%"
echo Folder: %~dp0                                               >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo.
echo   Street Lighting - road lighting design
echo   Looking for Python...
echo.
set "PY="
set "PYARGS="
call :try "py" "-3"
call :try "python" ""
call :try "python3" ""
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :try "%%~D\python.exe" ""
for /d %%D in ("%ProgramFiles%\Python3*")                 do call :try "%%~D\python.exe" ""
for /d %%D in ("C:\Python3*")                             do call :try "%%~D\python.exe" ""
call :try "%USERPROFILE%\anaconda3\python.exe" ""
call :try "%USERPROFILE%\miniconda3\python.exe" ""
call :try "%USERPROFILE%\AppData\Local\anaconda3\python.exe" ""
call :try "C:\ProgramData\anaconda3\python.exe" ""
call :try "C:\ProgramData\miniconda3\python.exe" ""
call :try "%USERPROFILE%\Anaconda3\python.exe" ""
call :try "C:\Anaconda3\python.exe" ""
if not defined PY goto nopython
echo   Using: %PY% %PYARGS%
>>"%LOG%" echo   Using: %PY% %PYARGS%
"%PY%" %PYARGS% -c "import numpy" >nul 2>>"%LOG%"
if not errorlevel 1 goto haveNumpy
echo   Installing numpy (needed for the calculations)...
"%PY%" %PYARGS% -m pip install numpy >>"%LOG%" 2>&1
:haveNumpy
echo   Starting Street Lighting in your browser. Leave this window open while you work.
echo   Other computers on your network can use it too (add --lan).
echo.
"%PY%" %PYARGS% server.py 2>>"%LOG%"
>>"%LOG%" echo Server exit code: %ERRORLEVEL%
echo.
echo   Street Lighting has stopped. If this was unexpected, the file
echo   startup_log.txt in this folder has the details.
echo.
pause
exit /b 0

:nopython
echo.
echo   Python was not found on this computer.
echo   Install Python 3.9 or newer from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" during the installation.
echo   Details: %LOG%
echo No working Python interpreter found. >> "%LOG%"
pause
exit /b 1

:try
if defined PY goto :eof
set "CAND=%~1"
set "CARGS=%~2"
>>"%LOG%" echo --- trying: %CAND% %CARGS%
"%CAND%" %CARGS% -c "import sys; print(sys.version)" >>"%LOG%" 2>&1
if errorlevel 1 goto :eof
set "PY=%CAND%"
set "PYARGS=%CARGS%"
>>"%LOG%" echo *** SELECTED: %CAND% %CARGS%
goto :eof
