package com.curdeg.channel.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.curdeg.channel.data.TokenStore
import com.curdeg.channel.ui.HomeScreen
import com.curdeg.channel.ui.LoginScreen
import com.curdeg.channel.ui.MeScreen
import com.curdeg.channel.ui.NotificationsScreen
import com.curdeg.channel.ui.PostDetailScreen
import kotlinx.coroutines.flow.first

object Routes {
    const val LOGIN = "login"
    const val HOME = "home"
    const val POST = "post/{id}"
    const val NOTIFICATIONS = "notifications"
    const val ME = "me"
    fun post(id: Long) = "post/$id"
}

@Composable
fun AppNav(modifier: Modifier = Modifier) {
    val nav = rememberNavController()
    var authed by remember { mutableStateOf<Boolean?>(null) }

    LaunchedEffect(Unit) {
        authed = TokenStore.accessToken.first() != null
    }

    authed?.let { loggedIn ->
        NavHost(navController = nav, startDestination = if (loggedIn) Routes.HOME else Routes.LOGIN, modifier = modifier) {
            composable(Routes.LOGIN) { LoginScreen(onLoggedIn = { nav.navigate(Routes.HOME) { popUpTo(0) } }) }
            composable(Routes.HOME) { HomeScreen(nav) }
            composable(Routes.POST) { entry ->
                val id = entry.arguments?.getString("id")?.toLongOrNull() ?: 0L
                PostDetailScreen(nav, id)
            }
            composable(Routes.NOTIFICATIONS) { NotificationsScreen(nav) }
            composable(Routes.ME) { MeScreen(onLoggedOut = { nav.navigate(Routes.LOGIN) { popUpTo(0) } }) }
        }
    }
}
