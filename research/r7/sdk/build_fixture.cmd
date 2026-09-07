@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b %errorlevel%
cd /d "%~dp0"
cl /nologo /std:c++17 /Zc:__cplusplus /O2 /MD /EHsc ..\sources\kernel_access\verify_fixture.cpp /Foverify_fixture.obj /Feverify_fixture.exe
exit /b %errorlevel%
