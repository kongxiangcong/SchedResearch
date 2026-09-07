@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b %errorlevel%
cd /d "%~dp0"
if not exist ..\bin mkdir ..\bin
cl /nologo /std:c++17 /Zc:__cplusplus /O2 /MD /EHsc /Iinclude ..\copy_probe.cpp /Fo..\bin\copy_probe.obj /Fe..\bin\copy_probe.exe /link lib\xrt_coreutil.lib bcrypt.lib
exit /b %errorlevel%
