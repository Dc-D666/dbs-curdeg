# Retrofit/Gson 反射保留规则（release 混淆时使用）
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.curdeg.channel.data.** { *; }
-keep class com.google.gson.reflect.TypeToken { *; }
-keep class * extends com.google.gson.reflect.TypeToken
-dontwarn okhttp3.**
-dontwarn retrofit2.**
