@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b %errorlevel%
cd /d "%~dp0"
lib /nologo /machine:x64 /def:lib\xrt_coreutil.def /out:lib\xrt_coreutil.lib
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c++17 /Zc:__cplusplus /O2 /MD /EHsc /Iinclude xclbin_metadata.cpp /Fexclbin_metadata.exe /link lib\xrt_coreutil.lib
exit /b %errorlevel%
