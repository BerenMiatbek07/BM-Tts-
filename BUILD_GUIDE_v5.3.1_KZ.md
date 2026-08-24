# BM Text to Voice v5.3.1 — Windows-та APK/AAB жинау

## Дайын релиз параметрлері

- Package: `org.bmtts.bmtextspeech`
- Version name: `5.3.1`
- Version code: `102640925`
- Minimum Android: API 26 (Android 8)
- Target Android: API 36 (Android 16)
- Архитектура: `arm64-v8a`
- Google Play форматы: production `.aab`
- Телефонға тексеру форматы: test-ad `.apk`

## Осы компьютерде қолданылған құралдар

1. Windows 10/11 және WSL2 Ubuntu.
2. JDK 17.
3. Android SDK, Build Tools және Platform API 36.
4. Android NDK r25b, 16 KB page-size-пен жиналған native кітапханалар.
5. Python 3.12 — source тесттері үшін.
6. `adb` — телефон мен BlueStacks-қа орнату үшін.
7. `D:\keystore\bmquiz.keystore` — Play Console-дағы бұрынғы қолданбамен бірдей қолтаңба үшін.

Keystore паролін ешбір `.py`, `.sh` немесе `.md` файлына жазбаңыз. Ол build кезінде тек `KS_PASS` орта айнымалысы арқылы беріледі.

## Source тексеру

PowerShell ішінде project бумасын ашыңыз:

```powershell
cd "C:\path\to\project"
python -m py_compile main.py
python -m pytest -q
wsl.exe bash -n ./build_bmtts_v520_complete_cached.sh
```

Күтілетін нәтиже: `10 passed`, Bash syntax error жоқ.

## Осы компьютердегі толық cached build

WSL жағында мына runtime жолдары дайын болуы керек:

- `/home/beren/bmtts_sherpa_16kb_clean_storage/dists/bmtextspeech16kb510sherpa`
- `/home/beren/.buildozer/android/platform/android-sdk`
- `/home/beren/android-ndk-r25b-16kb-v510-clean`
- `/home/beren/bmtts_build/project`

PowerShell сессиясында signing паролін уақытша енгізіп, WSL-ге өткізіңіз:

```powershell
$secure = Read-Host "Keystore password" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:KS_PASS = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  $env:WSLENV = "KS_PASS"
  wsl.exe bash ./tools/run_final_build.sh
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  Remove-Item Env:KS_PASS -ErrorAction SilentlyContinue
}
```

Build скрипті мыналарды автоматты тексереді:

- Python source compile;
- Java/Kivy/AdMob/Sherpa bridge файлдары;
- test APK ішінде Google test AdMob ID;
- production AAB ішінде live AdMob ID;
- APK/AAB қолтаңбасы;
- versionCode және targetSdk;
- барлық native `.so` файлдарының 16 KB alignment-ы;
- `private.tar` ішіндегі Python модульдері, PNG иконкалар, дауыс preview файлдары және CA сертификаты.

## Шығатын файлдар

```text
BM_Text_to_Voice_v5.3.1_102640925_STUDIO_TEST_signed.apk
BM_Text_to_Voice_v5.3.1_102640925_STUDIO_PROD_signed.aab
```

APK тек телефонға/эмуляторға тест жасауға арналған және Google test ads қолданады. Play Console-ға тек `STUDIO_PROD_signed.aab` жүктеледі.

## Телефонға орнатып тексеру

USB debugging қосылған телефон үшін:

```powershell
adb devices -l
adb -s DEVICE_SERIAL install -r "C:\path\BM_Text_to_Voice_v5.3.1_102640925_STUDIO_TEST_signed.apk"
adb -s DEVICE_SERIAL shell am start -W -n org.bmtts.bmtextspeech/.BmLaunchActivity
adb -s DEVICE_SERIAL shell dumpsys package org.bmtts.bmtextspeech | Select-String "versionCode|versionName"
```

## Қолданба жаңартуын хабарлау

Сайттың түбіріне `version.json` жариялау керек. Дайын мысал `website/version.json.example` ішінде. Нақты URL:

```text
https://YOUR-DOMAIN/version.json
```

Файл жарияланғаннан кейін `main.py` ішіндегі `UPDATE_CHECK_URLS` тізіміне дәл сол URL енгізіледі. HTTPS міндетті. Қолданба сертификатты тексеруді өшірмейді; APK ішіне Mozilla CA қоймасы енгізілген.
