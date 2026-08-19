package com.curdeg.channel

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.curdeg.channel.navigation.AppNav
import com.curdeg.channel.ui.theme.ChannelTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ChannelTheme {
                AppNav()
            }
        }
    }
}
