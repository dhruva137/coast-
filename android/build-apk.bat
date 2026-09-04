@echo off
setlocal
set "JAVA_HOME=C:\idr-build\jdk-17"
set "ANDROID_HOME=C:\idr-build\android-sdk"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%PATH%"
cd /d "%~dp0"
echo JAVA_HOME=%JAVA_HOME%
if not exist "%JAVA_HOME%\bin\java.exe" (
  echo JDK missing
  exit /b 1
)
call gradlew.bat %*
exit /b %ERRORLEVEL%
