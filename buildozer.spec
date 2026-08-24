[app]
title = BM Text to Voice TTS
package.name = bmtextspeech
package.domain = org.bmtts
source.dir = .
source.include_exts = py,png,jpg,json,atlas,jar,so,wav,mp3,pem
source.exclude_dirs = tests,bin,.buildozer,__pycache__,p4a_recipes,source_backup_before_v493,source_backup_before_v494,source_backup_before_v495
source.exclude_patterns = mobile_*_preview*.png,*.aar
version = 5.6.2
requirements = python3,kivy==2.3.0,websocket-client==1.8.0,certifi,requests==2.32.3,chardet==5.2.0,idna,urllib3
orientation = portrait
fullscreen = 0
icon.filename = assets/icon.png
presplash.filename = assets/icon.png
presplash.color = #080B10

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,WAKE_LOCK,RECORD_AUDIO,com.google.android.gms.permission.AD_ID
android.add_src = android_src
android.add_jars = libs/sherpa-onnx-1.13.4.jar
android.add_libs_arm64_v8a = libs/android-v8/*.so
android.gradle_dependencies = com.google.android.gms:play-services-ads:25.4.0,com.android.billingclient:billing:9.1.0,org.jetbrains.kotlin:kotlin-stdlib:1.7.10,org.apache.commons:commons-compress:1.26.2
android.meta_data = com.google.android.gms.ads.APPLICATION_ID=ca-app-pub-2408723079137167~4524564324
android.activity_class_name = org.bmtts.bmtextspeech.BmPythonActivity
android.wakelock = True
android.api = 36
android.numeric_version = 102640934
android.minapi = 26
android.ndk = 25b
android.ndk_api = 26
android.archs = arm64-v8a
android.accept_sdk_license = True
android.enable_androidx = True
android.private_storage = True
android.allow_backup = False
android.logcat_filters = *:S python:D
android.release_artifact = aab
p4a.branch = v2024.01.21
p4a.source_dir = /home/beren/bmtts_p4a_v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
