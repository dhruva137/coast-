package `in`.sih26168.idr.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

@Composable
fun AboutScreen() {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("IDR", fontFamily = IdrSans, color = Fg, fontSize = 28.sp)
        Text("INTELLIGENT DEAD RECKONING  ·  SIH 26168", fontFamily = IdrMono, color = Accent, fontSize = 11.sp, letterSpacing = 1.4.sp)
        Text(
            "v0.4.0 · on-device only. No network, no account, no analytics.",
            color = Telem,
            fontFamily = IdrMono,
            fontSize = 11.sp,
        )
        Text(
            "Smartphone dead reckoning for two-wheelers when GNSS dies. ISRO problem statement 26168.",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 14.sp,
        )

        Spacer(Modifier.height(4.dp))
        Text("WE CLAIM", fontFamily = IdrMono, color = Telem, fontSize = 11.sp, letterSpacing = 2.sp)
        Claim("First smartphone DR system that handles leaning two-wheelers.")
        Claim("Fixed-point coordinated-turn solver with cos(Δφ) insensitivity — heading-rate error tracks lean error, not lean angle.")
        Claim("Error budget: heading hurts 6.3× more than speed over 1 km.")
        Claim("Branch-decision accuracy as the user metric (did we take the right ramp), not only drift %.")

        Spacer(Modifier.height(4.dp))
        Text("WE DO NOT CLAIM", fontFamily = IdrMono, color = Danger, fontSize = 11.sp, letterSpacing = 2.sp)
        Claim("Discovery of roll/yaw kinematics — Titterton & Weston, textbook.")
        Claim("Invention of map-matching for tunnels — Newson & Krumm 2009.")
        Claim("First road-signature localisation, mount-angle estimation, or adaptive NHC.")

        Spacer(Modifier.height(4.dp))
        Text("BENCHMARK", fontFamily = IdrMono, color = Mute, fontSize = 11.sp, letterSpacing = 2.sp)
        Text(
            "<10% drift  ·  <100 m per km at 60 km/h  ·  10 Hz on-device",
            fontFamily = IdrMono,
            color = Fg,
            fontSize = 13.sp,
        )

        Spacer(Modifier.height(4.dp))
        Text("KNOWN LIMITS", fontFamily = IdrMono, color = Mute, fontSize = 11.sp, letterSpacing = 2.sp)
        Claim("Lean solver is simulation-validated; tan(φ) ≈ v·ψ̇/g must be tested on a real Indian scooter.")
        Claim("Hard braking mid-turn is the genuine failure mode.")
        Claim("The method needs speed; it composes with learned odometry, it does not replace it.")
        Claim("Magnetometer aiding is likely unusable on a two-wheeler.")
    }
}

@Composable
private fun Claim(text: String) {
    Text("·  $text", color = Fg, fontFamily = IdrSans, fontSize = 14.sp, lineHeight = 20.sp)
}
