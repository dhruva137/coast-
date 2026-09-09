package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * First-run walkthrough for somebody who has never seen this app.
 *
 * Five pages: what it does, what it needs and why, how to mount the phone,
 * the calibration run, and how to read the main screen. Skippable at every
 * step and re-openable from Help.
 *
 * The permissions page asks for the grants inline rather than describing them,
 * and is explicit that location is optional -- refusing it does not stop the
 * app, it changes the mode.
 */
@Composable
fun OnboardingScreen(
    bus: IdrBus,
    permsOk: Boolean,
    coarseOnly: Boolean = false,
    requestPerms: () -> Unit,
    onFinish: () -> Unit,
    onDemoMode: (() -> Unit)? = null,
) {
    var page by remember { mutableIntStateOf(0) }
    val last = 4

    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .padding(horizontal = 20.dp)
            .padding(top = 12.dp, bottom = 16.dp),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (i in 0..last) {
                    Box(
                        Modifier
                            .size(if (i == page) 10.dp else 7.dp)
                            .clip(CircleShape)
                            .background(if (i == page) Accent else Line),
                    )
                }
            }
            TextButton(onClick = onFinish) {
                Text("SKIP", fontFamily = IdrMono, color = Mute, fontSize = 12.sp)
            }
        }

        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(top = 12.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            when (page) {
                0 -> PageWhat(onDemoMode = onDemoMode)
                1 -> PagePermissions(bus, permsOk, coarseOnly, requestPerms)
                2 -> PageMount()
                3 -> PageCalibrate(bus)
                else -> PageReadScreen()
            }
        }

        Row(
            Modifier
                .fillMaxWidth()
                .padding(top = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (page > 0) {
                SecondaryButton("BACK", Modifier.weight(1f)) { page -= 1 }
            }
            Button(
                onClick = { if (page == last) onFinish() else page += 1 },
                modifier = Modifier
                    .weight(2f)
                    .height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
                shape = RoundedCornerShape(10.dp),
            ) {
                Text(
                    if (page == last) "START USING IT" else "NEXT",
                    fontFamily = IdrMono,
                    fontSize = 15.sp,
                    letterSpacing = 1.6.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

// ---------------------------------------------------------------------------

@Composable
private fun PageWhat(onDemoMode: (() -> Unit)? = null) {
    Title("It keeps navigating when GPS stops.")
    Body(
        "In a tunnel, a basement car park, or between tall buildings, satellite " +
            "positioning drops out and an ordinary map app freezes your marker. This " +
            "app carries on from the motion sensors in the phone and keeps showing " +
            "where you are going.",
    )
    if (onDemoMode != null) {
        Button(
            onClick = onDemoMode,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
            shape = RoundedCornerShape(10.dp),
        ) {
            Text(
                "DEMO MODE",
                fontFamily = IdrMono,
                fontSize = 16.sp,
                letterSpacing = 1.6.sp,
                fontWeight = FontWeight.Bold,
            )
        }
        Text(
            "One tap · no permissions · works offline",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 13.sp,
        )
    }
    Card(Telem) {
        Text(
            "What it will always tell you",
            fontFamily = IdrSans, color = Telem, fontSize = 14.sp, fontWeight = FontWeight.SemiBold,
        )
        Bullet("Which mode it is in: satellite fix, dead reckoning, or relative.")
        Bullet("How far off it might be, and whether that figure was measured or modelled.")
        Bullet("When it does not know something. It will not make a number up.")
    }
    Body(
        "It is built for two-wheelers, which lean into turns. Leaning is the thing " +
            "most dead-reckoning systems get wrong, and handling it properly is the " +
            "core of this project.",
    )
}

@Composable
private fun PagePermissions(bus: IdrBus, permsOk: Boolean, coarseOnly: Boolean, requestPerms: () -> Unit) {
    Title("What it needs, and why.")

    Card(Accent) {
        Text(
            "Motion sensors — required",
            fontFamily = IdrSans, color = Accent, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
        )
        Body(
            "The gyroscope and accelerometer are how the app knows you turned and how " +
                "fast you are going when there is no satellite fix. This is the whole " +
                "mechanism. Android grants these without a prompt, but the phone has to " +
                "actually have them.",
        )
    }

    Card(Amber) {
        Text(
            "Location — optional, and useful twice",
            fontFamily = IdrSans, color = Amber, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
        )
        Body(
            "First, for the starting fix that puts your route on the map. Second, for " +
                "re-acquiring: when you come out of the tunnel, a fresh fix snaps the " +
                "track back onto the world and resets the error to near zero.",
        )
        Body(
            "Refuse it and the app still runs. It will track distance and the shape of " +
                "your route, and say plainly that the position is relative rather than " +
                "absolute.",
        )
    }

    Card(Mute) {
        Text(
            "Notifications — optional",
            fontFamily = IdrSans, color = Fg, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
        )
        Body(
            "Only so tracking keeps running with the screen off. Nothing is sent " +
                "anywhere; the app has no server and works with the phone offline.",
        )
    }

    if (permsOk) {
        Text(
            if (coarseOnly) {
                "Approximate location granted — precision is reduced. Precise GPS is optional."
            } else {
                "Permissions granted."
            },
            fontFamily = IdrMono,
            color = if (coarseOnly) Amber else Telem,
            fontSize = 13.sp,
        )
    } else {
        Button(
            onClick = requestPerms,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
            shape = RoundedCornerShape(10.dp),
        ) {
            Text("GRANT PERMISSIONS", fontFamily = IdrMono, letterSpacing = 1.4.sp)
        }
        Text(
            "Or skip. You can grant them later, and the app is designed to be useful " +
                "without them.",
            fontFamily = IdrSans, color = Mute, fontSize = 12.sp, lineHeight = 16.sp,
        )
    }

    PrivacyNote()

    Spacer(Modifier.height(4.dp))
    Text(
        "YOUR PHONE",
        fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 2.sp,
    )
    DeviceCheckCard(bus = bus, compact = true)
}

@Composable
private fun PageMount() {
    Title("How should I hold the phone?")
    Body(
        "The short answer: fix it to something rigid. A phone that can slide or spin " +
            "reports motion the vehicle did not make, and the app has no way to tell " +
            "the difference.",
    )

    Card(Telem) {
        Text(
            "Best — a rigid mount",
            fontFamily = IdrSans, color = Telem, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
        )
        Bullet("A handlebar clamp on a scooter, motorcycle or bicycle.")
        Bullet("A dashboard cradle or a car air-vent mount.")
        Bullet("Anything that holds the phone still. Yes, a handlebar mount is worth buying.")
        Body(
            "The phone does not need to be upright or facing any particular way. It " +
                "needs to not move relative to the vehicle. The calibration step on the " +
                "next page works out the angle for you.",
        )
    }

    Card(Amber) {
        Text(
            "Workable — a pocket or a bag",
            fontFamily = IdrSans, color = Amber, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
        )
        Body(
            "It will run, with noticeably worse accuracy. A tight trouser pocket or a " +
                "zipped tank bag is far better than a loose jacket pocket or a backpack, " +
                "because the phone shifts less.",
        )
    }

    Card(Color(0xFFFF4D6A)) {
        Text(
            "Avoid",
            fontFamily = IdrSans, color = Color(0xFFFF4D6A), fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Bullet("Loose on a seat, in a cup holder, or rattling in an open bag.")
        Bullet("Held in your hand — your arm moves independently of the vehicle.")
        Bullet("Re-adjusting the phone mid-journey. If you must, calibrate again after.")
    }
}

@Composable
private fun PageCalibrate(bus: IdrBus) {
    Title("One short straight run.")
    Body(
        "Do this once for each way you mount the phone. It takes eight seconds and it " +
            "is what lets the app tell a real turn from the phone sitting at an angle.",
    )
    CalibrationCard(bus = bus)
    Body(
        "Walking in a straight line works for setting this up indoors. Redo it on the " +
            "vehicle when you can, because the mount angle is what is actually being " +
            "measured.",
    )
}

@Composable
private fun PageReadScreen() {
    Title("Reading the main screen.")

    Row(verticalAlignment = Alignment.Top) {
        Swatch(Telem)
        Column(Modifier.padding(start = 12.dp)) {
            Legend("GNSS")
            Body("A live satellite fix. Your position is absolute and the accuracy shown is the figure the phone itself reports.")
        }
    }
    Row(verticalAlignment = Alignment.Top) {
        Swatch(Accent)
        Column(Modifier.padding(start = 12.dp)) {
            Legend("DEAD RECKONING")
            Body("No fix, but the app knows where you started. Your position is still absolute and the error circle grows the further you go without a fix.")
        }
    }
    Row(verticalAlignment = Alignment.Top) {
        Swatch(Amber)
        Column(Modifier.padding(start = 12.dp)) {
            Legend("RELATIVE")
            Body("No fix and no starting point. Distance and the shape of your route are real, but the app does not know where on the Earth they are, and says so. You can give it a start point at any time.")
        }
    }

    Card(Mute) {
        Text("On the map", fontFamily = IdrSans, color = Fg, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        Bullet("The orange line is the app estimate. A dashed teal line, when present, is raw GPS, so you can see the two agree or disagree.")
        Bullet("The circle around the arrow is how far off you might be. Solid means measured by the phone; dashed means modelled from distance travelled.")
        Bullet("The small crosshair is where you started.")
        Bullet("The grid is real metres, and there is a scale bar. There is no street map — the app works with no network at all.")
    }

    Card(Mute) {
        Text("Buttons", fontFamily = IdrSans, color = Fg, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        Bullet("START begins tracking. It does not wait for GPS.")
        Bullet("SET START POINT anchors a relative route to coordinates you supply.")
        Bullet("MARK HERE drops a pin; ride back to it and CLOSE LOOP measures the real drift, which then replaces the modelled figure.")
        Bullet("DIAGNOSTICS opens every engineering readout: lean angle, inference latency, sustained rate, sensor rates, heading disagreement.")
    }
}

// ---------------------------------------------------------------------------

@Composable
private fun Title(text: String) {
    Text(
        text,
        fontFamily = IdrSans,
        color = Fg,
        fontSize = 26.sp,
        fontWeight = FontWeight.Bold,
        lineHeight = 32.sp,
    )
}

@Composable
private fun Body(text: String) {
    Text(
        text,
        fontFamily = IdrSans,
        color = Mute,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    )
}

@Composable
private fun Legend(text: String) {
    Text(text, fontFamily = IdrMono, color = Fg, fontSize = 13.sp, letterSpacing = 1.4.sp)
}

@Composable
private fun Bullet(text: String) {
    Text(
        "·  $text",
        fontFamily = IdrSans,
        color = Fg,
        fontSize = 13.sp,
        lineHeight = 19.sp,
    )
}

@Composable
private fun Swatch(color: Color) {
    Box(
        Modifier
            .padding(top = 4.dp)
            .size(12.dp)
            .clip(CircleShape)
            .background(color),
    )
}

@Composable
private fun Card(tint: Color, content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Bg2)
            .border(1.dp, tint.copy(alpha = 0.3f), RoundedCornerShape(14.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        content()
    }
}
