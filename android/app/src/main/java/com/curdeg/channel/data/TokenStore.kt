package com.curdeg.channel.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/** 登录态：access / refresh token 持久化（DataStore）。 */
object TokenStore {
    private val Context.dataStore by preferencesDataStore(name = "auth")

    private const val KEY_ACCESS = "sdu_access_token"
    private const val KEY_REFRESH = "sdu_refresh_token"
    private lateinit var appContext: Context

    fun init(context: Context) {
        appContext = context.applicationContext
    }

    val accessToken: Flow<String?> = appContext.dataStore.data.map { it[stringPreferencesKey(KEY_ACCESS)] }

    suspend fun save(access: String, refresh: String) {
        appContext.dataStore.edit {
            it[stringPreferencesKey(KEY_ACCESS)] = access
            it[stringPreferencesKey(KEY_REFRESH)] = refresh
        }
    }

    suspend fun clear() {
        appContext.dataStore.edit {
            it.remove(stringPreferencesKey(KEY_ACCESS))
            it.remove(stringPreferencesKey(KEY_REFRESH))
        }
    }
}
