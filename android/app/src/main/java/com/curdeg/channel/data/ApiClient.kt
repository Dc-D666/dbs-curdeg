package com.curdeg.channel.data

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/** 后端统一响应（code=0 成功，见 详细开发方案.md §5.1）。 */
data class ApiResponse<T>(
    val code: Int,
    val message: String,
    val data: T?,
) {
    fun requireData(): T = data ?: throw RuntimeException(message.ifBlank { "响应数据为空" })
}

object ApiClient {
    /** 线上地址；本地调试改为 http://10.0.2.2:8000 并给 manifest 加 cleartext。 */
    const val BASE_URL = "https://guild.weaxi.cn/api/v1/"

    private var tokenProvider: (() -> String?)? = null

    lateinit var service: ApiService
        private set

    fun init(tokenProvider: () -> String?) {
        this.tokenProvider = tokenProvider
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        val client = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val token = tokenProvider()
                val req = if (token.isNullOrBlank()) {
                    chain.request()
                } else {
                    chain.request().newBuilder()
                        .header("Authorization", "Bearer $token")
                        .build()
                }
                chain.proceed(req)
            }
            .addInterceptor(logging)
            .build()
        service = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }

    /** 取当前 token（供拦截器用）。 */
    fun currentToken(): String? = tokenProvider?.invoke()

    /** 从 Flow 同步取一次（应用启动后首次请求前）。 */
    fun tokenBlocking(): String? = runBlocking { TokenStore.accessToken.first() }
}
