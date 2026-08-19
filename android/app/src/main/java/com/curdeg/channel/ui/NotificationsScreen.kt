package com.curdeg.channel.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import coil.compose.AsyncImage
import com.curdeg.channel.data.ApiClient
import com.curdeg.channel.data.NotificationOut
import com.curdeg.channel.navigation.Routes

/** 通知中心：列表 + 未读标识 + 点击跳转。 */
@Composable
fun NotificationsScreen(nav: NavHostController) {
    var items by remember { mutableStateOf<List<NotificationOut>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        try {
            items = ApiClient.service.notifications().requireData().items
            ApiClient.service.readAll()
        } catch (_: Exception) {
        } finally {
            loading = false
        }
    }

    Scaffold(
        topBar = {
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { nav.popBackStack() }) { Icon(Icons.Filled.ArrowBack, "返回") }
                Text("通知中心", style = MaterialTheme.typography.titleMedium)
            }
        },
    ) { padding ->
        when {
            loading -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            items.isEmpty() -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { Text("暂无通知") }
            else -> LazyColumn(Modifier.fillMaxSize().padding(padding)) {
                items(items, key = { it.id }) { n ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable {
                                val ref = n.refId
                                if (ref != null) {
                                    when (n.type) {
                                        "comment", "like", "mention" -> nav.navigate(Routes.post(ref))
                                        else -> Unit // 频道/系统类暂不跳转
                                    }
                                }
                            }
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                    ) {
                        AsyncImage(
                            model = n.actorAvatar,
                            contentDescription = null,
                            modifier = Modifier.width(36.dp).height(36.dp).background(MaterialTheme.colorScheme.primaryContainer, CircleShape),
                            contentScale = ContentScale.Crop,
                        )
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text("${n.actorNickname} · ${n.title}", style = MaterialTheme.typography.bodyMedium, fontWeight = if (n.isRead) null else androidx.compose.ui.text.font.FontWeight.Bold)
                            if (n.summary.isNotBlank()) Text(n.summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                            Text(n.createdAt.take(16).replace('T', ' '), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                        }
                    }
                }
            }
        }
    }
}
