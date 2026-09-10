package `in`.sih26168.idr.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * Local profile gate — **no network, no real auth**.
 *
 * "Sign in" only stores a display name in [Prefs]. Console pairing is a
 * separate opt-in under Settings. Never add an HTTP client or analytics here.
 */
@Composable
fun AuthScreen(
    onFinished: () -> Unit,
    allowDismiss: Boolean = false,
    onDismiss: () -> Unit = {},
    onDemoMode: (() -> Unit)? = null,
) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    var email by remember { mutableStateOf(prefs.displayName) }
    var localName by remember { mutableStateOf(prefs.displayName) }

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Accent,
        unfocusedBorderColor = Line,
        focusedLabelColor = Accent,
        unfocusedLabelColor = Mute,
        cursorColor = Accent,
        focusedTextColor = Fg,
        unfocusedTextColor = Fg,
    )

    Column(
        Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(36.dp))
        Text(
            "COAST",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 32.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "INTELLIGENT DEAD RECKONING",
            fontFamily = IdrMono,
            color = Accent,
            fontSize = 11.sp,
            letterSpacing = 2.sp,
        )
        Text(
            "Local profile. No cloud account. Pairing a laptop console is optional.",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 14.sp,
        )

        Spacer(Modifier.height(8.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = Bg2),
            shape = RoundedCornerShape(16.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        ) {
            Column(
                Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                if (onDemoMode != null) {
                    Button(
                        onClick = onDemoMode,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Accent,
                            contentColor = Bg,
                        ),
                        shape = RoundedCornerShape(12.dp),
                    ) {
                        Text("TRY DEMO", fontFamily = IdrMono, letterSpacing = 1.2.sp)
                    }
                    Text(
                        "Skip setup. Replay a real GPS outage on the map.",
                        color = Mute,
                        fontFamily = IdrSans,
                        fontSize = 12.sp,
                    )
                }
                Button(
                    onClick = {
                        prefs.displayName = ""
                        prefs.authDone = true
                        localName = ""
                        onFinished()
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (onDemoMode != null) {
                            Accent.copy(alpha = 0.2f)
                        } else {
                            Accent
                        },
                        contentColor = if (onDemoMode != null) Accent else Bg,
                    ),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Text("CONTINUE AS GUEST", fontFamily = IdrMono, letterSpacing = 1.2.sp)
                }

                Text(
                    "OPTIONAL LOCAL SIGN-IN",
                    fontFamily = IdrMono,
                    color = Mute,
                    fontSize = 10.sp,
                    letterSpacing = 1.5.sp,
                )
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("Email (display name only)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = fieldColors,
                    shape = RoundedCornerShape(12.dp),
                )
                Button(
                    onClick = {
                        val trimmed = email.trim()
                        if (trimmed.isEmpty()) return@Button
                        prefs.displayName = trimmed
                        prefs.authDone = true
                        localName = trimmed
                        onFinished()
                    },
                    enabled = email.trim().isNotEmpty(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Accent.copy(alpha = 0.2f),
                        contentColor = Accent,
                    ),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Text("SIGN IN", fontFamily = IdrMono, letterSpacing = 1.2.sp)
                }

                if (localName.isNotBlank()) {
                    TextButton(
                        onClick = {
                            prefs.displayName = ""
                            localName = ""
                            email = ""
                            // Stay past the gate; this only clears the local label.
                        },
                    ) {
                        Text("CLEAR PROFILE", fontFamily = IdrMono, color = Mute, fontSize = 12.sp)
                    }
                }
            }
        }

        if (allowDismiss) {
            TextButton(onClick = onDismiss) {
                Text("BACK", fontFamily = IdrMono, color = Mute, fontSize = 12.sp)
            }
        }

        Spacer(Modifier.weight(1f))
        Text(
            "Device-local profile · zero account servers",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )
    }
}
