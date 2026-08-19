package com.curdeg.channel.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.curdeg.channel.data.ApiClient
import com.curdeg.channel.data.TokenStore
import kotlinx.coroutines.launch

/** 我的：用户资料 + 退出登录。 */
@Composable
fun MeScreen(onLoggedOut: () -> Unit) {
    var user by remember { mutableStateOf<com.curdeg.channel.data.UserOut?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        try {
            user = ApiClient.service.me().requireData()
        } catch (_: Exception) {
        }
    }

    Scaffold(
        topBar = {
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = {}) { Icon(Icons.Filled.ArrowBack, null) }
                Text("个人中心", style = MaterialTheme.typography.titleMedium)
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.height(24.dp))
            when (val u = user) {
                null -> CircularProgressIndicator()
                else -> {
                    AsyncImage(
                        model = u.avatarUrl,
                        contentDescription = null,
                        modifier = Modifier
                            .width(72.dp)
                            .height(72.dp),
                        contentScale = ContentScale.Crop,
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(u.nickname.ifBlank { u.username }, style = MaterialTheme.typography.titleLarge)
                    Text("@${u.username}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                    if (u.bio.isNotBlank()) {
                        Spacer(Modifier.height(8.dp))
                        Text(u.bio, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            Spacer(Modifier.height(40.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        TokenStore.clear()
                        onLoggedOut()
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("退出登录") }
        }
    }
}
