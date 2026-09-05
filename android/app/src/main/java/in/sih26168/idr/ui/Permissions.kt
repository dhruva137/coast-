package `in`.sih26168.idr.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
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
 *
 * `BODY_SENSORS` used to be in this list and in the manifest. It was never
 * needed -- an accelerometer and a gyroscope are not body sensors and Android
 * grants them without a prompt. Asking for a dangerous permission the code never
 * uses is the fastest way to make a stranger refuse the ones that matter.
 */
fun requiredPermissions(): Array<String> = locationPermissions() + notificationPermissions()

/** Optional. Refusing these changes the mode, it does not stop the app. */
fun locationPermissions(): Array<String> = arrayOf(
    Manifest.permission.ACCESS_FINE_LOCATION,
    Manifest.permission.ACCESS_COARSE_LOCATION,
)

/** API 33+ only. Needed so the ongoing "tracking is running" notice is visible. */
fun notificationPermissions(): Array<String> =
    if (Build.VERSION.SDK_INT >= 33) arrayOf(Manifest.permission.POST_NOTIFICATIONS) else emptyArray()

/**
 * Whether every permission is held, plus a lambda that asks for the lot.
 *
 * There is deliberately NO automatic request. The previous version fired the
 * system location dialog from a `LaunchedEffect` on first composition, so a
 * returning user was met with a permission sheet before the app had drawn
 * anything. A cold prompt with no context is what people refuse, and once
 * refused twice Android stops asking at all. Every request in this app now comes
 * from a control the user pressed, next to the sentence explaining it: the
 * GRANT PERMISSIONS button on the onboarding page, ALLOW LOCATION on the Drive
 * banner, or START asking for notifications only.
 */
@Composable
fun rememberPermissionGate(): Pair<Boolean, () -> Unit> {
    val ctx = LocalContext.current
    fun granted(): Boolean = requiredPermissions().all {
        ContextCompat.checkSelfPermission(ctx, it) == PackageManager.PERMISSION_GRANTED
    }
    var ok by remember { mutableStateOf(granted()) }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { ok = granted() }
    val request: () -> Unit = { launcher.launch(requiredPermissions()) }
    return ok to request
}

/**
 * A notification-only gate, used by the START buttons.
 *
 * Tracking runs with the screen off behind a foreground service, and a
 * foreground service the user cannot see in the shade is exactly the behaviour
 * that makes an app look like spyware. Asking at the moment the user starts
 * tracking is the one point where the reason is self-evident. Returns a no-op
 * requester below API 33, where the permission does not exist.
 */
@Composable
fun rememberNotificationGate(): Pair<Boolean, () -> Unit> {
    val ctx = LocalContext.current
    val needed = notificationPermissions()
    fun granted(): Boolean = needed.all {
        ContextCompat.checkSelfPermission(ctx, it) == PackageManager.PERMISSION_GRANTED
    }
    var ok by remember { mutableStateOf(granted()) }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { ok = granted() }
    val request: () -> Unit = {
        if (needed.isNotEmpty() && !ok) launcher.launch(needed)
    }
    return ok to request
}
