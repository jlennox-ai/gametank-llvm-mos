@echo off
rem Builds this folder with the environment's build.py: build.bat, or build.bat debug.
rem Python's launcher (py) picks the newest Python 3 installed; without it, python on the PATH.
setlocal
set "PYTHON=python"
where py >nul 2>&1 && set "PYTHON=py -3"
%PYTHON% "%~dp0..\build.py" "%~dp0." %*
