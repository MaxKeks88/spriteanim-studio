@echo off
rem Сборка APK SpriteAnim Studio. Нужен JDK 17+ (берём из Android Studio) и Android SDK.
setlocal
set "HERE=%~dp0"

if not defined JAVA_HOME (
  if exist "%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe" (
    set "JAVA_HOME=%ProgramFiles%\Android\Android Studio\jbr"
  )
)
if not defined JAVA_HOME (
  echo [!] Не найден JDK. Установите Android Studio или задайте JAVA_HOME.
  exit /b 1
)

if not exist "%HERE%local.properties" (
  if exist "%LOCALAPPDATA%\Android\Sdk" (
    > "%HERE%local.properties" echo sdk.dir=%LOCALAPPDATA:\=/%/Android/Sdk
  ) else (
    echo [!] Не найден Android SDK: %LOCALAPPDATA%\Android\Sdk
  )
)

call "%HERE%gradlew.bat" assembleDebug %*
if errorlevel 1 exit /b 1

echo.
echo Готово: %HERE%app\build\outputs\apk\debug\app-debug.apk
echo Установка на телефон: adb install -r "%HERE%app\build\outputs\apk\debug\app-debug.apk"
endlocal
