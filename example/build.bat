@echo off
rem Builds this project with its CMake preset: build.bat (release, into build\) or build.bat debug
rem (into build-debug\).
setlocal
set "PRESET=%~1"
if "%PRESET%"=="" set "PRESET=release"
pushd "%~dp0"
cmake --preset %PRESET% && cmake --build --preset %PRESET%
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
