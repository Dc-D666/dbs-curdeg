package com.curdeg.channel.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// 品牌色对齐 Web 端 TDesign token（#0052d9）
private val Brand = Color(0xFF0052D9)
private val BrandHover = Color(0xFF366EF4)
private val Danger = Color(0xFFD54941)

private val LightColors = lightColorScheme(
    primary = Brand,
    secondary = BrandHover,
    error = Danger,
    background = Color(0xFFF3F3F3),
    surface = Color(0xFFFFFFFF),
    onPrimary = Color.White,
)

@Composable
fun ChannelTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = LightColors,
        content = content,
    )
}
