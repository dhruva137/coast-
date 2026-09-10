package `in`.sih26168.idr.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import `in`.sih26168.idr.data.ThemePreference

private val DarkScheme = darkColorScheme(
    primary = Accent,
    onPrimary = Bg,
    secondary = Telem,
    onSecondary = Bg,
    background = Bg,
    onBackground = Text,
    surface = Bg2,
    onSurface = Text,
    surfaceVariant = Bg2,
    onSurfaceVariant = Mute,
    outline = Line,
    error = Danger,
    onError = Text,
    tertiary = Ours,
    scrim = Color(0xCC07090D),
)

/** Light scheme on the same teal accent — secondary to dark for demos. */
private val LightScheme = lightColorScheme(
    primary = Accent,
    onPrimary = Color.White,
    secondary = Color(0xFF008F6A),
    onSecondary = Color.White,
    background = Color(0xFFF4F6F8),
    onBackground = Color(0xFF0B0E11),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF0B0E11),
    surfaceVariant = Color(0xFFE8ECF0),
    onSurfaceVariant = Color(0xFF5A6570),
    outline = Color(0xFFC5CDD6),
    error = Danger,
    onError = Color.White,
    tertiary = Gnss,
    scrim = Color(0x6607090D),
)

/** Current theme preference; Drive map reads this for basemap light/dark. */
val LocalThemePreference = staticCompositionLocalOf { ThemePreference.Dark }

fun resolveDarkTheme(preference: ThemePreference, systemDark: Boolean): Boolean =
    when (preference) {
        ThemePreference.System -> systemDark
        ThemePreference.Light -> false
        ThemePreference.Dark -> true
    }

@Composable
fun IdrTheme(
    preference: ThemePreference = ThemePreference.Dark,
    content: @Composable () -> Unit,
) {
    val systemDark = isSystemInDarkTheme()
    val dark = resolveDarkTheme(preference, systemDark)
    val ctx = LocalContext.current
    val scheme = if (Build.VERSION.SDK_INT >= 31) {
        // Dynamic colour on API 31+; custom teal schemes otherwise / as fallback.
        runCatching {
            if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        }.getOrElse { if (dark) DarkScheme else LightScheme }
    } else {
        if (dark) DarkScheme else LightScheme
    }

    CompositionLocalProvider(LocalThemePreference provides preference) {
        MaterialTheme(
            colorScheme = scheme,
            typography = IdrTypography,
            content = content,
        )
    }
}
