package com.curdeg.channel.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.curdeg.channel.data.ApiClient
import com.curdeg.channel.data.ApiResponse
import com.curdeg.channel.data.LoginRequest
import com.curdeg.channel.data.RegisterRequest
import com.curdeg.channel.data.SendCodeRequest
import com.curdeg.channel.data.TokenOut
import com.curdeg.channel.data.TokenStore
import kotlinx.coroutines.launch

/** 登录 / 注册（邮箱验证码）。 */
@Composable
fun LoginScreen(onLoggedIn: () -> Unit) {
    var tab by remember { mutableIntStateOf(0) }
    var account by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(48.dp))
        Text("频道社区", style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.primary)
        Text("SDUdiscord · 仿腾讯频道课设", style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(24.dp))

        TabRow(selectedTabIndex = tab) {
            Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("登录") })
            Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("注册") })
        }
        Spacer(Modifier.height(16.dp))

        if (tab == 0) {
            OutlinedTextField(account, { account = it }, Modifier.fillMaxWidth(), label = { Text("用户名或邮箱") })
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                password, { password = it }, Modifier.fillMaxWidth(),
                label = { Text("密码") },
                visualTransformation = PasswordVisualTransformation(),
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        msg = null
                        try {
                            val res = ApiClient.service.login(LoginRequest(account, password))
                            handleToken(res, onLoggedIn, { msg = it })
                        } catch (e: Exception) {
                            msg = e.message ?: "网络错误"
                        } finally {
                            busy = false
                        }
                    }
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth(),
            ) { if (busy) CircularProgressIndicator(Modifier.height(20.dp)) else Text("登录") }
        } else {
            OutlinedTextField(username, { username = it }, Modifier.fillMaxWidth(), label = { Text("用户名（3-32 位字母数字下划线）") })
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(email, { email = it }, Modifier.fillMaxWidth(), label = { Text("邮箱") })
            Spacer(Modifier.height(8.dp))
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(code, { code = it }, Modifier.fillMaxWidth(), label = { Text("验证码") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                Button(onClick = {
                    scope.launch {
                        try {
                            ApiClient.service.sendCode(SendCodeRequest(email))
                            msg = "验证码已发送"
                        } catch (e: Exception) {
                            msg = e.message ?: "发送失败"
                        }
                    }
                }) { Text("发送验证码") }
            }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                password, { password = it }, Modifier.fillMaxWidth(),
                label = { Text("密码（至少 6 位，含字母和数字）") },
                visualTransformation = PasswordVisualTransformation(),
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        msg = null
                        try {
                            val res = ApiClient.service.register(RegisterRequest(username, email, code, password))
                            handleToken(res, onLoggedIn, { msg = it })
                        } catch (e: Exception) {
                            msg = e.message ?: "网络错误"
                        } finally {
                            busy = false
                        }
                    }
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth(),
            ) { if (busy) CircularProgressIndicator(Modifier.height(20.dp)) else Text("注册") }
        }

        msg?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }
    }
}

private suspend fun handleToken(res: ApiResponse<TokenOut>, onLoggedIn: () -> Unit, onError: (String) -> Unit) {
    if (res.code != 0 || res.data == null) {
        onError(res.message)
        return
    }
    TokenStore.save(res.data.accessToken, res.data.refreshToken)
    onLoggedIn()
}
