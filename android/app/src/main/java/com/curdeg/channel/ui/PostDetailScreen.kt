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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import coil.compose.AsyncImage
import com.curdeg.channel.data.ApiClient
import com.curdeg.channel.data.CommentOut
import com.curdeg.channel.data.CreateCommentRequest
import com.curdeg.channel.data.LikeRequest
import com.curdeg.channel.data.PostOut
import com.curdeg.channel.navigation.Routes
import kotlinx.coroutines.launch

/** 帖子详情：富文本/图片渲染 + 评论列表 + 点赞。 */
@Composable
fun PostDetailScreen(nav: NavHostController, postId: Long) {
    val scope = rememberCoroutineScope()
    var post by remember { mutableStateOf<PostOut?>(null) }
    var comments by remember { mutableStateOf<List<CommentOut>>(emptyList()) }
    var input by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(postId) {
        try {
            post = ApiClient.service.postDetail(postId).requireData()
            comments = ApiClient.service.comments(postId).requireData().items
        } catch (_: Exception) {
        } finally {
            loading = false
        }
    }

    Scaffold(
        topBar = {
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { nav.popBackStack() }) { Icon(Icons.Filled.ArrowBack, "返回") }
                Text("帖子", style = MaterialTheme.typography.titleMedium)
            }
        },
    ) { padding ->
        if (loading) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else if (post == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { Text("帖子不存在") }
        } else {
            val p = post!!
            Column(Modifier.fillMaxSize().padding(padding)) {
                LazyColumn(Modifier.weight(1f)) {
                    item {
                        Column(Modifier.padding(16.dp)) {
                            Text(p.title, style = MaterialTheme.typography.headlineSmall)
                            Spacer(Modifier.height(6.dp))
                            Text("${p.authorNickname} · ${p.communityName} · ${p.createdAt.take(16).replace('T', ' ')}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                            Spacer(Modifier.height(10.dp))
                            // 富文本：简单按文本分片渲染（图片单独九宫格）
                            p.richContent.forEach { seg ->
                                val text = seg["text"] as? String ?: return@forEach
                                if (text.isNotBlank()) Text(text, style = MaterialTheme.typography.bodyLarge)
                            }
                            if (p.richContent.isEmpty() && p.sourceMarkdown.isNotBlank()) {
                                Text(p.sourceMarkdown, style = MaterialTheme.typography.bodyLarge)
                            }
                            if (p.images.isNotEmpty()) {
                                Spacer(Modifier.height(8.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    p.images.take(3).forEach { url ->
                                        AsyncImage(model = url, contentDescription = null, modifier = Modifier.width(100.dp).height(100.dp), contentScale = ContentScale.Crop)
                                    }
                                }
                            }
                            Spacer(Modifier.height(10.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                OutlinedButton(onClick = {
                                    scope.launch {
                                        try {
                                            val res = ApiClient.service.like(LikeRequest(p.id)).requireData()
                                            post = p.copy(likeCount = res.count, isLiked = res.liked)
                                        } catch (_: Exception) {
                                        }
                                    }
                                }) { Text(if (p.isLiked) "已赞 ${p.likeCount}" else "点赞 ${p.likeCount}") }
                                Text("${p.commentCount} 评论", Modifier.align(Alignment.CenterVertically), style = MaterialTheme.typography.bodySmall)
                            }
                            Spacer(Modifier.height(12.dp))
                            Text("评论", style = MaterialTheme.typography.titleMedium)
                            Spacer(Modifier.height(4.dp))
                        }
                    }
                    items(comments, key = { it.id }) { c ->
                        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                            AsyncImage(model = c.authorAvatar, contentDescription = null, modifier = Modifier.width(30.dp).height(30.dp).background(MaterialTheme.colorScheme.primaryContainer, CircleShape), contentScale = ContentScale.Crop)
                            Spacer(Modifier.width(8.dp))
                            Column {
                                Text(c.authorNickname, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                                Text(c.content, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
                Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(input, { input = it }, Modifier.weight(1f), placeholder = { Text("说点什么…") })
                    OutlinedButton(
                        enabled = input.isNotBlank() && !sending,
                        onClick = {
                            sending = true
                            scope.launch {
                                try {
                                    ApiClient.service.createComment(p.id, CreateCommentRequest(input.trim()))
                                    comments = comments + CommentOut(System.currentTimeMillis(), input.trim(), 0, "我", "", 0)
                                    input = ""
                                } catch (_: Exception) {
                                } finally {
                                    sending = false
                                }
                            }
                        },
                    ) { Text("发送") }
                }
            }
        }
    }
}
