@echo off
rem Builds this project with its CMake preset: build.bat (release, into build\) or build.bat debug
rem (into build-debug\). GAMETANK_LLVM_MOS, the gametank-llvm-mos folder, is the one above this one
rem unless it's already set.
setlocal
if not defined GAMETANK_LLVM_MOS set "GAMETANK_LLVM_MOS=%~dp0.."
set "PRESET=%~1"
if "%PRESET%"=="" set "PRESET=release"
pushd "%~dp0"
cmake --preset %PRESET% && cmake --build --preset %PRESET%
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
