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
 * Location and notifications are **separate** asks. Bundling them made Android
 * 13+ report "not granted" after the user only allowed location (POST_NOTIFICATIONS
 * still missing). The Drive banner must use [rememberLocationPermissionGate].
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
 * Location-only gate for the Drive / onboarding "Allow location" path.
 *
 * [onResult] fires after every system dialog result so callers can refresh
 * [in.sih26168.idr.IdrBus.location] immediately (banner clears without Start).
 */
@Composable
fun rememberLocationPermissionGate(
    onResult: (granted: Boolean) -> Unit = {},
): Pair<Boolean, () -> Unit> {
    val ctx = LocalContext.current
    val needed = locationPermissions()
    fun granted(): Boolean = needed.all {
        ContextCompat.checkSelfPermission(ctx, it) == PackageManager.PERMISSION_GRANTED
    }
    var ok by remember { mutableStateOf(granted()) }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) {
        ok = granted()
        onResult(ok)
    }
    val request: () -> Unit = { launcher.launch(needed) }
    return ok to request
}

/**
 * @deprecated Prefer [rememberLocationPermissionGate] for location UI and
 * [rememberNotificationGate] at Start. Kept for any call site that still wants
 * the combined list (should not drive the location banner).
 */
@Composable
fun rememberPermissionGate(): Pair<Boolean, () -> Unit> = rememberLocationPermissionGate()

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
