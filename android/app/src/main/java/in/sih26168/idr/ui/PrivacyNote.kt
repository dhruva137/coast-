package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * The privacy note.
 *
 * Every sentence here is a statement about this build that can be checked
 * against the code, and each was checked before it was written:
 *
 *  * `INTERNET` is declared for public OSM/Carto basemap tiles only; with
 *    basemap off, network traffic is zero. Position, sensors, logs and sessions
 *    never leave the device on the standard flavour.
 *  * There is no analytics, crash reporting or advertising library.
 *  * `allowBackup` is false and both backup rule files exclude everything, so
 *    ride logs are not swept into a cloud backup either.
 *
 * If any of that stops being true, this text has to change in the same commit.
 */
@Composable
fun PrivacyNote(modifier: Modifier = Modifier) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Bg2)
            .border(1.dp, Telem.copy(alpha = 0.3f), RoundedCornerShape(14.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            "Everything stays on this phone",
            fontFamily = IdrSans,
            color = Telem,
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Line(
            "INTERNET is declared for public OSM/Carto basemap tiles only; with " +
                "basemap off, network traffic is zero. Your position and session " +
                "logs never leave this phone.",
        )
        Line(
            "There is no account, no server, no cloud and no analytics. Nobody, " +
                "including us, can see where you went.",
        )
        Line(
            "The trained model runs here, on the phone's own processor, from a file " +
                "inside the app. Nothing is sent away to be computed.",
        )
        Line(
            "Navigating records nothing at all. Only the RECORD tab writes files, " +
                "and it tells you where they go.",
        )
        Line(
            "Ride logs are excluded from Android backup and device transfer. They " +
                "leave the phone only if you choose SHARE on a session yourself.",
        )
    }
}

/**
 * What RECORD actually writes, named exactly, shown next to the button that
 * starts it. [sessionDir] is the real path once a session exists.
 */
@Composable
fun RecordDataDisclosure(sessionDir: String?, modifier: Modifier = Modifier) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Bg2)
            .border(1.dp, Mute.copy(alpha = 0.25f), RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            "WHAT RECORDING WRITES TO THIS PHONE",
            fontFamily = IdrMono,
            color = Telem,
            fontSize = 10.sp,
            letterSpacing = 1.6.sp,
        )
        Line("imu.csv — raw accelerometer, gyroscope, compass, pressure and light readings, at the full sensor rate.")
        Line("gnss.csv — every GPS fix: latitude, longitude, altitude, speed, bearing, accuracy, satellite count. This is a record of where you went.")
        Line("meta.json — rider name, route id, vehicle, mount and phone model, exactly as you typed them.")
        Line("quality.json — the automatic pass/fail score, written when you press stop.")
        Text(
            sessionDir ?: "Android/data/in.sih26168.idr/files/data/<rider>/<vehicle>/<timestamp>/",
            fontFamily = IdrMono,
            color = Fg,
            fontSize = 10.sp,
            lineHeight = 14.sp,
        )
        Line(
            "That folder belongs to this app. Uninstalling deletes it. Nothing is " +
                "uploaded — use SESSIONS to delete a log, or to zip and share one " +
                "deliberately.",
        )
    }
}

@Composable
private fun Line(text: String) {
    Text(
        "·  $text",
        fontFamily = IdrSans,
        color = Mute,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    )
}
