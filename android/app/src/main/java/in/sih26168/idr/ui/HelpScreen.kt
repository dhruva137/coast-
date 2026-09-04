package `in`.sih26168.idr.ui

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
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * The re-openable half of onboarding: replay the walkthrough, re-run the
 * hardware check, re-do the mount calibration, and read the project claims.
 */
@Composable
fun HelpScreen(bus: IdrBus, onReplayOnboarding: () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
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
            "No. There is no server and no map download. The trained model runs on the " +
                "phone. The map is a metre grid rather than street tiles precisely so that " +
                "it cannot go blank when the network does.",
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
            "Offline street tiles were not shipped in this build, and a map that needs " +
                "wifi is worse than no map at a venue with none. Every distance drawn is a " +
                "real measured distance on a metre grid.",
        )

        Header("ABOUT THE PROJECT")
        AboutScreen()
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
