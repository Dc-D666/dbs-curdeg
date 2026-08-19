package com.curdeg.channel

import android.app.Application
import com.curdeg.channel.data.ApiClient
import com.curdeg.channel.data.TokenStore

class ChannelApp : Application() {
    override fun onCreate() {
        super.onCreate()
        TokenStore.init(this)
        ApiClient.init(TokenStore::accessToken)
    }
}
