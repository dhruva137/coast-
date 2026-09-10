package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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

internal const val ONBOARDING_LAST_PAGE = 1

/**
 * First-run, two beats: what the app does, then location in context.
 * Primary finish is Try Demo. Mount / calibration / HUD legend live in Help.
 */
@Composable
fun OnboardingScreen(
    permsOk: Boolean,
    coarseOnly: Boolean = false,
    requestPerms: () -> Unit,
    onFinish: () -> Unit,
    onDemoMode: (() -> Unit)? = null,
) {
    var page by remember { mutableIntStateOf(0) }
    val last = ONBOARDING_LAST_PAGE

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
                0 -> PageWhat()
                else -> PageLocation(permsOk, coarseOnly, requestPerms)
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
                onClick = {
                    when {
                        page < last -> page += 1
                        onDemoMode != null -> onDemoMode()
                        else -> onFinish()
                    }
                },
                modifier = Modifier
                    .weight(2f)
                    .height(52.dp)
                    .semantics {
                        contentDescription = if (page < last) "Next" else "Try Demo"
                    },
                colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
                shape = RoundedCornerShape(10.dp),
            ) {
                Text(
                    when {
                        page < last -> "NEXT"
                        onDemoMode != null -> "TRY DEMO"
                        else -> "GET STARTED"
                    },
                    fontFamily = IdrMono,
                    fontSize = 15.sp,
                    letterSpacing = 1.6.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

@Composable
private fun PageWhat() {
    Title("When GPS dies, the dot keeps moving.")
    Body(
        "Tunnels, basements, and streets between tall buildings drop satellite " +
            "lock. A normal map freezes your marker. This app keeps it travelling " +
            "from the motion sensors in the phone.",
    )
    Card(Telem) {
        Text(
            "That is the whole product",
            fontFamily = IdrSans, color = Telem, fontSize = 14.sp, fontWeight = FontWeight.SemiBold,
        )
        Bullet("A live satellite fix while you have one.")
        Bullet("When the fix drops, the same dot coasts on sensors plus the road map.")
        Bullet("It will say when a position is relative, not invent a street.")
    }
    Body("Built for two-wheelers that lean into turns — the case most phone GPS apps get wrong.")
}

@Composable
private fun PageLocation(permsOk: Boolean, coarseOnly: Boolean, requestPerms: () -> Unit) {
    Title("Put yourself on the map.")
    Body(
        "Location is how the first pin lands on a real street, and how the track " +
            "snaps back when you leave a tunnel. It is not a wall of grants — " +
            "notifications wait until you press Start.",
    )
    Card(Amber) {
        Text(
            "Optional, and useful",
            fontFamily = IdrSans, color = Amber, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
        )
        Body(
            "Refuse it and the app still runs. Distance and the shape of the ride " +
                "stay real; the position is labelled relative instead of absolute.",
        )
    }

    if (permsOk) {
        Text(
            if (coarseOnly) {
                "Approximate location on — precise GPS is optional."
            } else {
                "Location allowed."
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
                .height(52.dp)
                .semantics { contentDescription = "Allow location" },
            colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
            shape = RoundedCornerShape(10.dp),
        ) {
            Text("ALLOW LOCATION", fontFamily = IdrMono, letterSpacing = 1.4.sp)
        }
        Text(
            "Or skip. You can allow it later from the map.",
            fontFamily = IdrSans, color = Mute, fontSize = 12.sp, lineHeight = 16.sp,
        )
    }
}

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
