# BM Voice Studio v5.5.2 — APK/AAB жинау

Қажет: Windows 10/11, WSL2 Ubuntu, Java 17, Android SDK/API 36, Python және жеке PKCS12 keystore.

## 1. Тест

```powershell
python -m pytest -q
```

Күтілетін нәтиже: `33 passed`.

## 2. Телефонға сынақ APK

```bash
export KS_PASS='СІЗДІҢ_KEYSTORE_ПАРОЛІҢІЗ'
cd /mnt/c/path/to/project
bash ./tools/build_phone_test.sh
unset KS_PASS
```

Шығыс: `Downloads/BM_Text_to_Voice_v5.5.2_PHONE_TEST.apk`.

## 3. Play Console AAB және production APK

```bash
export KS_PASS='СІЗДІҢ_KEYSTORE_ПАРОЛІҢІЗ'
cd /mnt/c/path/to/project
bash ./build_bmtts_v520_complete_cached.sh
bash ./tools/build_production_apk.sh
unset KS_PASS
```

Play Console-ға `BM_Text_to_Voice_v5.5.2_102640930_STUDIO_PROD_signed.aab`, телефонға `BM_Text_to_Voice_v5.5.2_102640930_PRODUCTION_signed.apk` орнатылады.

Скрипт `private.tar` ішіне ағымдағы Python/Java кодын қайта салады және APK ішіндегі `5.5.2` runtime-нұсқасын тексереді. Негізгі тексерулер: versionCode `102640930`, targetSdk `36`, қолтаңба, production AdMob ID және барлық native ELF үшін 16 KB page alignment.
