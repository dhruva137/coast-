package `in`.sih26168.idr.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat

/**
 * Permissions the app asks for. None of them gate tracking: the estimator arms
 * on the motion sensors, which need no runtime grant, and every refusal is
 * handled as a named mode rather than an error.
 */
fun requiredPermissions(): Array<String> = buildList {
    add(Manifest.permission.ACCESS_FINE_LOCATION)
    add(Manifest.permission.ACCESS_COARSE_LOCATION)
    add(Manifest.permission.BODY_SENSORS)
    if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
}.toTypedArray()

/**
 * @param autoRequest fire the system dialog on first composition. False during
 * onboarding, where the permission page explains what each grant is for before
 * asking -- a cold prompt on launch is exactly what a first-time user refuses.
 */
@Composable
fun rememberPermissionGate(autoRequest: Boolean = true): Pair<Boolean, () -> Unit> {
    val ctx = LocalContext.current
    fun granted(): Boolean = requiredPermissions().all {
        ContextCompat.checkSelfPermission(ctx, it) == PackageManager.PERMISSION_GRANTED
    }
    var ok by remember { mutableStateOf(granted()) }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { ok = granted() }
    val request: () -> Unit = { launcher.launch(requiredPermissions()) }
    LaunchedEffect(autoRequest) {
        if (autoRequest && !ok) request()
    }
    return ok to request
}
