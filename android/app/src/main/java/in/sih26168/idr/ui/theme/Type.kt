package `in`.sih26168.idr.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * Platform fonts only.
 *
 * This used to pull IBM Plex through Play Services downloadable fonts. That is a
 * network fetch, and it was the ONLY thing in the app that needed the INTERNET
 * permission. Keeping it would have meant either shipping a privacy note that
 * was not quite true, or explaining a network permission in an app whose entire
 * pitch is that it works with the phone offline. The instrument look comes from
 * the monospace family, which every Android device already has, so it also
 * cannot fail to arrive at a venue with no wifi.
 *
 * If the team ever wants Plex specifically, bundle the .ttf files in
 * `res/font/` -- that is offline and needs no permission. Do not put the
 * downloadable-font provider back.
 */
val IdrMono: FontFamily = FontFamily.Monospace

val IdrSans: FontFamily = FontFamily.SansSerif

val IdrTypography = Typography(
    displayLarge = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Bold, fontSize = 28.sp, letterSpacing = 0.4.sp, color = Text),
    titleLarge = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, color = Text),
    titleMedium = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Medium, fontSize = 16.sp, color = Text),
    bodyLarge = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Normal, fontSize = 15.sp, color = Text),
    bodyMedium = TextStyle(fontFamily = IdrSans, fontWeight = FontWeight.Normal, fontSize = 13.sp, color = Text),
    labelSmall = TextStyle(fontFamily = IdrMono, fontWeight = FontWeight.Medium, fontSize = 11.sp, letterSpacing = 1.2.sp, color = Mute),
    labelMedium = TextStyle(fontFamily = IdrMono, fontWeight = FontWeight.Medium, fontSize = 12.sp, color = Telem),
)
