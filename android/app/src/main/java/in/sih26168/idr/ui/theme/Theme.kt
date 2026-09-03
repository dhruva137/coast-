package `in`.sih26168.idr.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Scheme = darkColorScheme(
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

@Composable
fun IdrTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = Scheme,
        typography = IdrTypography,
        content = content,
    )
}
