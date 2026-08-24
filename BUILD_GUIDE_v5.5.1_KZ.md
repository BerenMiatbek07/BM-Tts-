# BM Voice Studio v5.5.1 — APK/AAB жинау

## Қажет құралдар

- Windows 10/11 және WSL2 Ubuntu
- Java 17
- Android SDK, Build Tools және API 36
- Python 3.11/3.12 (тесттер үшін)
- Жеке PKCS12 keystore

Бұл жобада Android/Kivy build кэші пайдаланылған. Негізгі жинақ скрипті Python кодын, Java bridge файлдарын, Sherpa-ONNX кітапханасын және 16 KB native кітапханаларды бір пакетке жинайды.

## Алдымен тест

PowerShell ішінде жоба папкасына кіріңіз:

```powershell
python -m pytest -q
```

Күтілетін нәтиже: `30 passed`.

## Телефонға арналған debug/test APK

WSL ішінде keystore паролін тек ағымдағы терминалға беріңіз. Парольді кодқа немесе Git-ке жазбаңыз:

```bash
export KS_PASS='СІЗДІҢ_KEYSTORE_ПАРОЛІҢІЗ'
cd /mnt/c/path/to/project
bash ./tools/build_phone_test.sh
unset KS_PASS
```

Шығыс файл:

```text
C:\Users\<user>\Downloads\BM_Text_to_Voice_v5.5.1_PHONE_TEST.apk
```

USB debugging қосулы телефонға орнату:

```powershell
adb install --no-incremental -r BM_Text_to_Voice_v5.5.1_PHONE_TEST.apk
```

## Қолтаңбаланған APK және Play Console AAB

```bash
export KS_PASS='СІЗДІҢ_KEYSTORE_ПАРОЛІҢІЗ'
cd /mnt/c/path/to/project
bash ./build_bmtts_v520_complete_cached.sh
bash ./tools/build_production_apk.sh
unset KS_PASS
```

Play Console-ға `...STUDIO_PROD_signed.aab`, ал телефонға қолмен орнатуға
`...PRODUCTION_signed.apk` пайдаланылады. `PHONE_TEST.apk` пен
`STUDIO_TEST_signed.apk` тек сынақ жарнамасына арналған.

Скрипт мыналарды автоматты тексереді:

- versionName `5.5.1`, versionCode `102640929`
- targetSdk `36`
- APK/AAB қолтаңбасы
- production AAB ішінде live AdMob идентификаторы
- барлық native ELF файлдарының 16 KB page alignment сәйкестігі

## Дауыс клондау моделі

Клондау engine-і модельді қолданбаның private storage бөлігіне жүктейді. Жүктеу аяқталғаннан кейін интернетсіз жұмыс істейді. Қазіргі ресми ZipVoice моделі тек ағылшын және қытай мәтініне арналған, сондықтан clone генерациясы UI ішінде ағылшын тілімен шектеледі. Қазақша, орысша және өзге тілдерді жалған түрде қолдайды деп көрсетпеңіз.

Телефондағы алғашқы модель жүктелуі RAM/жад жылдамдығына байланысты біраз уақыт алуы мүмкін. Жүктеу мен орнату кезінде қолданба экранды белсенді ұстайды және аяқталмаған файлды келесі іске қосқанда жалғастырады.
