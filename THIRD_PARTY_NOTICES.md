# Үшінші тарап компоненттері

Бұл source пакетінде қолданбаның build-іне қажет үшінші тарап binary файлдары бар:

- sherpa-onnx Android AAR/JAR және arm64-v8a native кітапханалары;
- ONNX Runtime native кітапханасы;
- build кезінде Gradle арқылы алынатын Google Mobile Ads SDK;
- build кезінде Gradle арқылы алынатын Apache Commons Compress.

Қосымша дауыс модельдері source архивіне немесе APK-ға салынбайды. Қолданба
оларды sherpa-onnx ресми `tts-models` каталогынан пайдаланушы таңдаған кезде
жүктейді. Әр модель архивінде өзінің лицензиясы болуы мүмкін. Модельді қайта
тарату немесе коммерциялық пайдалану алдында сол модельдің лицензиясын
тексеру қажет.

## OpenVoice V2 (Windows дауыс клондау)

Windows нұсқасындағы дауыс реңкін түрлендіру MyShell.ai OpenVoice V2
компонентін қолданады. Copyright 2024 MyShell.ai. Бұл компонент MIT
лицензиясымен таратылады: бағдарламаны пайдалануға, өзгертуге және
коммерциялық таратуға рұқсат беріледі; copyright пен лицензия ескертуі
сақталуы керек. Компонент ешқандай кепілдіксіз ұсынылады.

Ресми жоба: https://github.com/myshell-ai/OpenVoice
Ресми модель: https://huggingface.co/myshell-ai/OpenVoiceV2

## OmniVoice (жеке Windows жинағы)

Жеке Windows жинағы қазақша native cloning үшін k2-fsa/OmniVoice моделін
жүктей алады. Бұл мүмкіндік тек жеке, коммерциялық емес пайдалануға арналған;
Google Play/AAB жинағына модель кірмейді. Модельді монетизацияланған контентке,
ақылы қызметке немесе жария коммерциялық дистрибутивке қолдануға болмайды.
Қолданушы жүктеу алдында дауысқа құқығы бар екенін растауы тиіс.

Ресми жоба: https://github.com/k2-fsa/OmniVoice
Модель: https://huggingface.co/k2-fsa/OmniVoice

## Soniox web TTS / pysoniox protocol reference (personal Windows build)

The personal Windows build contains an independently written compatibility
client for Soniox's public text-to-speech web endpoint.  The request shape and
voice catalogue were cross-checked against the public `davidsuragan/pysoniox`
project.  No Soniox API key is embedded in this source package.  Soniox is an
external service and may change, rate-limit, or remove its web endpoint at any
time.  This compatibility integration is intended for the owner's personal
use only and is not a representation of an official Soniox SDK or partnership.

## ElevenLabs Eleven v3 (official API, personal Windows build)

Жеке Windows жинағында ElevenLabs-тың ресми Text-to-Speech API endpoint-і
қолданылады (`model_id=eleven_v3`). Пайдаланушы өз API key-ін қолданба
ішінде енгізеді; пакетке ешқандай API key салынбайды. Қазақша (`kk`),
орысша (`ru`) және ағылшынша (`en`) тіл кодтары жіберіледі.

Пайдаланушы көрсеткен `davidsuragan/elevenlabs-alpha-v3` репозиторийіндегі
voice ID мысалдары тек каталог үлгісі ретінде пайдаланылды. Репозиторийдің
API/login шектеулерін айналып өтуге арналған browser-header, Firebase немесе
Playwright bypass әдістері бұл жинаққа көшірілген жоқ. Eleven v3 қазір
ElevenLabs ресми API-інде қолжетімді болғандықтан, интеграция тек құжатталған
API арқылы жасалды. Қолдану ElevenLabs аккаунтының жоспары, квотасы және
қызмет шарттарына тәуелді.
