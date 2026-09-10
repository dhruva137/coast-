package `in`.sih26168.idr.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * Re-openable from Settings only (not a tab, not on Drive). Replay the
 * walkthrough, re-run the hardware check, and re-do mount calibration.
 * Project claims live under Settings → About.
 */
@Composable
fun HelpScreen(
    bus: IdrBus,
    onReplayOnboarding: () -> Unit,
    onBack: (() -> Unit)? = null,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        if (onBack != null) {
            Text(
                "← SETTINGS",
                modifier = Modifier
                    .padding(bottom = 4.dp)
                    .clickable(onClick = onBack),
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 11.sp,
                letterSpacing = 1.sp,
            )
        }
        Text(
            "Help",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 26.sp,
            fontWeight = FontWeight.Bold,
        )

        SecondaryButton("REPLAY THE WALKTHROUGH", Modifier.fillMaxWidth(), onReplayOnboarding)

        Header("THIS PHONE")
        DeviceCheckCard(bus = bus, compact = false)

        Header("MOUNT CALIBRATION")
        CalibrationCard(bus = bus)

        Header("PRIVACY")
        PrivacyNote()

        Header("QUICK ANSWERS")
        Qa(
            "Do I need a handlebar mount?",
            "It is the best option and it is worth buying one. A rigid clamp, a dashboard " +
                "cradle or a car vent mount all work. A pocket or a zipped bag works with " +
                "reduced accuracy. What matters is that the phone cannot slide or rotate " +
                "relative to the vehicle.",
        )
        Qa(
            "Does it work with location switched off?",
            "Yes. It tracks distance and the shape of your route from the motion sensors " +
                "and labels the position relative rather than absolute. You can anchor the " +
                "route to real coordinates at any time with SET START POINT.",
        )
        Qa(
            "Does it need the internet?",
            "Navigation does not. INTERNET is declared for public OSM/Carto basemap " +
                "tiles and, if you opt in, laptop-console pairing. With basemap off and " +
                "no pair, network traffic is zero. There is no cloud account and no " +
                "analytics. The trained speed model runs on the phone.",
        )
        Qa(
            "What does it record, and where does it go?",
            "Navigating on the DRIVE tab records nothing to disk. The RECORD tool " +
                "(under Settings) writes raw sensor and GPS readings to CSV files in this " +
                "app's own folder. Pairing, if you scan a console QR, streams live lat/lon " +
                "to that laptop only — never a device ID. Uninstalling the app deletes " +
                "local logs.",
        )
        Qa(
            "What does the accuracy figure mean?",
            "With a satellite fix it is the horizontal accuracy the operating system " +
                "reports, and it is labelled MEASURED. Without one it is MODELLED: the " +
                "accuracy of the last fix plus a percentage of the distance travelled " +
                "since. That percentage is a target until you close a loop, at which point " +
                "the app uses the drift it actually measured on your ride.",
        )
        Qa(
            "Why is there no street map?",
            "There is — OpenStreetMap tiles when Basemap is on in Settings. Turn it " +
                "off for a metre grid that works with the radio off. Offline mbtiles ship " +
                "with Demo Mode for the UK clip.",
        )

        Text(
            "Project claims and limits are under Settings → About.",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 13.sp,
            lineHeight = 18.sp,
        )
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun Header(text: String) {
    Text(
        text,
        fontFamily = IdrMono,
        color = Telem,
        fontSize = 11.sp,
        letterSpacing = 2.sp,
        modifier = Modifier.padding(top = 6.dp),
    )
}

@Composable
private fun Qa(question: String, answer: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            question,
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
            lineHeight = 20.sp,
        )
        Text(
            answer,
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 13.sp,
            lineHeight = 19.sp,
        )
    }
}
