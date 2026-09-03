@ECHO OFF
SETLOCAL
SET DIRNAME=%~dp0
IF "%DIRNAME%"=="" SET DIRNAME=.
SET APP_HOME=%DIRNAME%
FOR %%i IN ("%APP_HOME%") DO SET APP_HOME=%%~fi
SET APP_BASE_NAME=%~n0
SET DEFAULT_JVM_OPTS=-Dfile.encoding=UTF-8 "-Xmx64m" "-Xms64m"
SET JAVA_EXE=java.exe
IF DEFINED JAVA_HOME (
  SET JAVA_EXE=%JAVA_HOME%/bin/java.exe
  IF NOT EXIST "%JAVA_EXE%" (
    ECHO ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME%
    EXIT /B 1
  )
) ELSE (
  java.exe -version >NUL 2>&1
  IF ERRORLEVEL 1 (
    ECHO ERROR: JAVA_HOME is not set and no 'java' command could be found in PATH.
    EXIT /B 1
  )
)
SET CLASSPATH=%APP_HOME%\gradle\wrapper\gradle-wrapper.jar
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% "-Dorg.gradle.appname=%APP_BASE_NAME%" -classpath "%CLASSPATH%" org.gradle.wrapper.GradleWrapperMain %*
ENDLOCAL
EXIT /B %ERRORLEVEL%
