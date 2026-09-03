package `in`.sih26168.idr.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.googlefonts.Font
import androidx.compose.ui.text.googlefonts.GoogleFont
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.R

/**
 * IBM Plex via Play Services downloadable fonts. If GMS/network is missing,
 * Compose falls back to the platform default; we still set [FontFamily.Monospace]
 * as the HUD family so the instrument look holds offline at the venue.
 */
private val provider = GoogleFont.Provider(
    providerAuthority = "com.google.android.gms.fonts",
    providerPackage = "com.google.android.gms",
    certificates = R.array.com_google_android_gms_fonts_certs,
)

private val plexSans = FontFamily(
    Font(googleFont = GoogleFont("IBM Plex Sans"), fontProvider = provider, weight = FontWeight.Normal),
    Font(googleFont = GoogleFont("IBM Plex Sans"), fontProvider = provider, weight = FontWeight.Medium),
    Font(googleFont = GoogleFont("IBM Plex Sans"), fontProvider = provider, weight = FontWeight.SemiBold),
    Font(googleFont = GoogleFont("IBM Plex Sans"), fontProvider = provider, weight = FontWeight.Bold),
)

val IdrMono: FontFamily = FontFamily(
    Font(googleFont = GoogleFont("IBM Plex Mono"), fontProvider = provider, weight = FontWeight.Normal),
    Font(googleFont = GoogleFont("IBM Plex Mono"), fontProvider = provider, weight = FontWeight.Medium),
    Font(googleFont = GoogleFont("IBM Plex Mono"), fontProvider = provider, weight = FontWeight.SemiBold),
)

val IdrSans: FontFamily = plexSans

val IdrTypography = Typography(
    displayLarge = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Bold, fontSize = 28.sp, letterSpacing = 0.4.sp, color = Text),
    titleLarge = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, color = Text),
    titleMedium = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Medium, fontSize = 16.sp, color = Text),
    bodyLarge = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Normal, fontSize = 15.sp, color = Text),
    bodyMedium = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Normal, fontSize = 13.sp, color = Text),
    labelSmall = TextStyle(fontFamily = IdrMono, fontWeight = FontWeight.Medium, fontSize = 11.sp, letterSpacing = 1.2.sp, color = Mute),
    labelMedium = TextStyle(fontFamily = IdrMono, fontWeight = FontWeight.Medium, fontSize = 12.sp, color = Telem),
)
