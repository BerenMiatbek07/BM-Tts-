# BM Text to Voice v5.3.1 — соңғы тест есебі

## Автоматты тесттер

- `python -m py_compile main.py` — өтті.
- `python -m pytest -q` — 10/10 өтті.
- Bash build syntax — өтті.
- APK және AAB private runtime тексеруі — өтті.
- APK/AAB барлық native ELF 16 KB alignment — өтті.
- Production AAB live AdMob manifest — өтті.
- Test APK Google test AdMob manifest — өтті.

## Құрылғы тесттері

### vivo V2419, Android 15

- APK орнатылды және cold start орындалды.
- PID сақталды, FATAL EXCEPTION және ANR жоқ.
- UI толық portrait режимінде ашылды.
- Дәл жаңа dark navy/violet BM Voice Studio стилі көрінді.
- Дауыс моделін таңдау терезесі ашылды.
- Әр дауыс жолында жеке Play иконкасы бар.
- Isеке Play басылғанда bundled нақты үлгі ойнатылды.
- Picker жабылған жоқ және таңдалған Дәулет өзгерген жоқ.
- SSL certificate verification қатесі соңғы пакетте қайталанбады.

### BlueStacks Android 9

- APK орнатылды.
- versionCode `102640925`, versionName `5.3.1`, targetSdk `36` расталды.
- Қолданба ашылып, 18 секунд ішінде құламады.
- FATAL EXCEPTION, ANR және SSL verification қатесі жоқ.
- Жаңа дизайн үлкен экранда да дұрыс көрсетілді.

## Дыбыстама тесттері

- Дәулет online TTS және timecode generation бұрынғы regression тестінде өтті.
- Екі timecode бөлігі parallel жасалып, бір 8 секундтық mono PCM16 24 kHz WAV-қа біріктірілді.
- Isеке және Раяның телефонда бұрын жасалған нақты үлгілері осы APK-ға preview ретінде енгізілді.
- Ұзақ мәтін chunk/merge, session, сақтау және player логикасы Python тесттерінен өтті.

## Сервер жағындағы қалған қадам

Қолданбадағы update checker дайын, бірақ сайтқа `version.json` файлын жариялау қажет. Тексеру кезінде Netlify `/version.json` мекенжайы 404 қайтарды, ал `bmtts.org` DNS-та ашылмады. Бұл қолданбаны құлатпайды және қолданушыға raw error көрсетілмейді.
