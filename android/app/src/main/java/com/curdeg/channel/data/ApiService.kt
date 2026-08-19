package com.curdeg.channel.data

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/** 与后端 /api/v1 对应的接口定义（字段 snake_case ↔ Gson @SerializedName）。 */
interface ApiService {

    // ---------- 认证 ----------
    @POST("auth/send-code")
    suspend fun sendCode(@Body body: SendCodeRequest): ApiResponse<Unit>

    @POST("auth/register")
    suspend fun register(@Body body: RegisterRequest): ApiResponse<TokenOut>

    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): ApiResponse<TokenOut>

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): ApiResponse<TokenOut>

    // ---------- 用户 ----------
    @GET("users/me")
    suspend fun me(): ApiResponse<UserOut>

    // ---------- 频道 / 帖子 ----------
    @GET("feed")
    suspend fun globalFeed(
        @Query("sort") sort: String = "latest",
        @Query("cursor") cursor: String? = null,
        @Query("page_size") pageSize: Int = 20,
    ): ApiResponse<FeedPage>

    @GET("posts/{id}")
    suspend fun postDetail(@Path("id") id: Long): ApiResponse<PostOut>

    @POST("posts/{id}/comments")
    suspend fun createComment(@Path("id") id: Long, @Body body: CreateCommentRequest): ApiResponse<CommentOut>

    @GET("posts/{id}/comments")
    suspend fun comments(@Path("id") id: Long, @Query("page") page: Int = 1): ApiResponse<Page<CommentOut>>

    @POST("likes")
    suspend fun like(@Body body: LikeRequest): ApiResponse<LikeOut>

    @POST("follows")
    suspend fun follow(@Body body: FollowRequest): ApiResponse<Unit>

    // ---------- 通知 ----------
    @GET("notifications")
    suspend fun notifications(@Query("page") page: Int = 1): ApiResponse<Page<NotificationOut>>

    @GET("notifications/unread-count")
    suspend fun unreadCount(): ApiResponse<UnreadOut>

    @POST("notifications/read-all")
    suspend fun readAll(): ApiResponse<Unit>
}

// ---------- 请求体 ----------

data class SendCodeRequest(val email: String)
data class RegisterRequest(val username: String, val email: String, val code: String, val password: String)
data class LoginRequest(val account: String, val password: String)
data class RefreshRequest(@SerializedName("refresh_token") val refreshToken: String)
data class CreateCommentRequest(val content: String)
data class LikeRequest(@SerializedName("post_id") val postId: Long?)
data class FollowRequest(@SerializedName("community_id") val communityId: Long)

// ---------- 响应 ----------

data class TokenOut(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("expires_in") val expiresIn: Int,
)

data class UserOut(
    val id: Long,
    val username: String,
    val nickname: String,
    @SerializedName("avatar_url") val avatarUrl: String,
    val bio: String,
    @SerializedName("user_type") val userType: Int,
)

data class Page<T>(val items: List<T>, val total: Int, val page: Int, @SerializedName("page_size") val pageSize: Int)

data class FeedPage(
    val items: List<PostOut>,
    @SerializedName("next_cursor") val nextCursor: String?,
    @SerializedName("has_more") val hasMore: Boolean,
)

data class PostOut(
    val id: Long,
    val title: String,
    @SerializedName("community_id") val communityId: Long,
    @SerializedName("community_name") val communityName: String,
    @SerializedName("author_id") val authorId: Long,
    @SerializedName("author_nickname") val authorNickname: String,
    @SerializedName("author_avatar") val authorAvatar: String,
    @SerializedName("rich_content") val richContent: List<Map<String, Any>>,
    @SerializedName("source_markdown") val sourceMarkdown: String,
    val images: List<String>,
    @SerializedName("like_count") val likeCount: Int,
    @SerializedName("comment_count") val commentCount: Int,
    @SerializedName("is_liked") val isLiked: Boolean = false,
    @SerializedName("is_followed") val isFollowed: Boolean = false,
    @SerializedName("is_top") val isTop: Boolean = false,
    @SerializedName("is_essence") val isEssence: Boolean = false,
    @SerializedName("created_at") val createdAt: String,
)

data class CommentOut(
    val id: Long,
    val content: String,
    @SerializedName("author_id") val authorId: Long,
    @SerializedName("author_nickname") val authorNickname: String,
    @SerializedName("author_avatar") val authorAvatar: String,
    @SerializedName("like_count") val likeCount: Int,
    @SerializedName("is_liked") val isLiked: Boolean = false,
)

data class LikeOut(val liked: Boolean, val count: Int)

data class UnreadOut(val count: Int)

data class NotificationOut(
    val id: Long,
    val type: String,
    @SerializedName("actor_nickname") val actorNickname: String,
    @SerializedName("actor_avatar") val actorAvatar: String,
    @SerializedName("ref_id") val refId: Long?,
    val title: String,
    val summary: String,
    @SerializedName("is_read") val isRead: Boolean,
    @SerializedName("created_at") val createdAt: String,
)
