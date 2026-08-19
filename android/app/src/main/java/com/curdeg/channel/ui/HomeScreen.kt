package com.curdeg.channel.ui

import androidx.compose.foundation.background
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
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import coil.compose.AsyncImage
import com.curdeg.channel.data.ApiClient
import com.curdeg.channel.data.FeedPage
import com.curdeg.channel.data.PostOut
import com.curdeg.channel.navigation.Routes

/** 首页：全站帖子流（latest/hot）+ 底部导航（首页/通知/我的）。 */
@Composable
fun HomeScreen(nav: NavHostController) {
    var sort by remember { mutableStateOf("latest") }
    var feed by remember { mutableStateOf<FeedPage?>(null) }
    var unread by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(sort) {
        loading = true
        try {
            feed = ApiClient.service.globalFeed(sort = sort)
        } catch (e: Exception) {
            feed = null
        } finally {
            loading = false
        }
    }
    LaunchedEffect(Unit) {
        try {
            unread = ApiClient.service.unreadCount().requireData().count
        } catch (_: Exception) {
        }
    }

    Scaffold(
        topBar = {
            Column {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("频道社区", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.primary)
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(if (sort == "latest") "最新" else "热门", Modifier.clickable { sort = if (sort == "latest") "hot" else "latest" }, color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(selected = true, onClick = {}, icon = { Icon(androidx.compose.material.icons.Icons.Filled.Home, null) }, label = { Text("首页") })
                NavigationBarItem(
                    selected = false,
                    onClick = { nav.navigate(Routes.NOTIFICATIONS) },
                    icon = {
                        BadgedBox(badge = { if (unread > 0) Badge { Text(if (unread > 99) "99+" else "$unread") } }) {
                            Icon(androidx.compose.material.icons.Icons.Filled.Notifications, null)
                        }
                    },
                    label = { Text("通知") },
                )
                NavigationBarItem(selected = false, onClick = { nav.navigate(Routes.ME) }, icon = { Icon(androidx.compose.material.icons.Icons.Filled.Person, null) }, label = { Text("我的") })
            }
        },
    ) { padding ->
        when {
            loading -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            feed == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { Text("加载失败，请检查网络") }
            feed!!.items.isEmpty() -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { Text("暂无帖子") }
            else -> LazyColumn(Modifier.fillMaxSize().padding(padding)) {
                items(feed!!.items, key = { it.id }) { post ->
                    PostCard(post, onClick = { nav.navigate(Routes.post(post.id)) })
                }
                if (feed!!.hasMore) {
                    item {
                        var more by remember { mutableStateOf(false) }
                        if (!more) {
                            LaunchedEffect(Unit) {
                                more = true
                                try {
                                    val next = ApiClient.service.globalFeed(sort = sort, cursor = feed!!.nextCursor)
                                    feed = feed!!.copy(items = feed!!.items + next.items, nextCursor = next.nextCursor, hasMore = next.hasMore)
                                } catch (_: Exception) {
                                }
                            }
                        }
                        Box(Modifier.fillMaxWidth().padding(12.dp), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator(Modifier.height(20.dp))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun PostCard(post: PostOut, onClick: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(
                model = post.authorAvatar,
                contentDescription = null,
                modifier = Modifier
                    .width(32.dp)
                    .height(32.dp)
                    .background(MaterialTheme.colorScheme.primaryContainer, CircleShape),
                contentScale = ContentScale.Crop,
            )
            Spacer(Modifier.width(8.dp))
            Column {
                Text(post.authorNickname, style = MaterialTheme.typography.bodySmall)
                Text("${post.communityName} · ${post.createdAt.take(10)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(post.title, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(4.dp))
        Text(
            post.sourceMarkdown.ifBlank { "查看详情…" },
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (post.images.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            AsyncImage(model = post.images.first(), contentDescription = null, modifier = Modifier.fillMaxWidth().height(140.dp), contentScale = ContentScale.Crop)
        }
        Spacer(Modifier.height(8.dp))
        Text("👍 ${post.likeCount}  💬 ${post.commentCount}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
    }
}
