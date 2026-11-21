# Сборка APK

## Что нужно

- **JDK 17+**. На этой машине подходит `C:\Program Files\Android\Android Studio\jbr`
  (Java 25).
- **Android SDK** в `%LOCALAPPDATA%\Android\Sdk` (платформа 36, build-tools 36).
- Всё остальное уже лежит в `android/` (Gradle wrapper 9.7, AGP 9.3.1).

## Быстрая сборка

```bat
cd android
build-apk.bat
```

или:

```bat
cd android
set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
gradlew.bat assembleDebug
```

Готовый файл: `android\app\build\outputs\apk\debug\app-debug.apk`.

`build-apk.bat` сам подставляет `JAVA_HOME` из Android Studio и создаёт
`local.properties` с путём к SDK, если его нет. `local.properties` в этой папке
намеренно не лежит — путь к SDK у каждой машины свой.

В VS Code: **Terminal → Run Task → «Собрать APK (Android)»** (задача лежит в
корне проекта, не в этой папке).

## Установка на телефон

По USB:

```bat
"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" install -r android\app\build\outputs\apk\debug\app-debug.apk
```

Без USB: скопировать APK на телефон и открыть файл.

## Версия

В `android/app/build.gradle`:

```groovy
versionCode 4
versionName "0.4.1-mobile"
```

`versionCode` обязан расти при каждой установке поверх — иначе Android не
поставит новую сборку.

## Release-подпись (если понадобится)

Сейчас release-сборка тоже подписана debug-ключом. Для нормальной подписи:

```bat
keytool -genkeypair -v -keystore release.jks -alias spriteanim ^
        -keyalg RSA -keysize 2048 -validity 10000
```

Затем в `app/build.gradle`:

```groovy
android {
    signingConfigs {
        release {
            storeFile file("../../release.jks")
            storePassword "…"
            keyAlias "spriteanim"
            keyPassword "…"
        }
    }
    buildTypes {
        release { signingConfig signingConfigs.release }
    }
}
```

и `gradlew.bat assembleRelease`. Keystore и пароли храните отдельно: без них
не будет обновлений поверх (только удалить и установить заново).

## Что не входит в папку

- `android/build/`, `android/app/build/`, `android/.gradle/` — кэш сборки.
- `android/local.properties` — путь к SDK этой машины.
- Серверная часть (`server.py`, `ui/`) — она в корне проекта, см. `SERVER.md`.
