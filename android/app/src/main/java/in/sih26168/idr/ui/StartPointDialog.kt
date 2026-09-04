package `in`.sih26168.idr.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.OriginSource
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * Anchor a relative track to a point on the Earth.
 *
 * There is no basemap to long-press onto (see [DriveMap]), so a long press on
 * the map opens this instead of pretending the canvas is georeferenced. The
 * user either reuses the last real fix or types coordinates from another source
 * -- a paper map, a sign, a companion phone.
 *
 * The dialog is explicit that a hand-set start point is an assertion, not a
 * measurement, because that is exactly how the error model treats it.
 */
@Composable
fun StartPointDialog(
    hud: HudState,
    onDismiss: () -> Unit,
    onSet: (Double, Double) -> Unit,
    onUseFix: () -> Unit,
    onClear: () -> Unit,
) {
    val haveFix = hud.lat.isFinite() && hud.lon.isFinite()
    var latText by remember {
        mutableStateOf(if (haveFix) "%.6f".format(hud.lat) else "")
    }
    var lonText by remember {
        mutableStateOf(if (haveFix) "%.6f".format(hud.lon) else "")
    }
    val lat = latText.trim().toDoubleOrNull()
    val lon = lonText.trim().toDoubleOrNull()
    val valid = lat != null && lon != null &&
        lat >= -90.0 && lat <= 90.0 && lon >= -180.0 && lon <= 180.0

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Accent,
        unfocusedBorderColor = Line,
        focusedLabelColor = Accent,
        unfocusedLabelColor = Mute,
        cursorColor = Accent,
        focusedTextColor = Fg,
        unfocusedTextColor = Fg,
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Bg2,
        title = {
            Text("Set your start point", fontFamily = IdrSans, color = Fg, fontSize = 19.sp)
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    "The app already knows how far you have travelled and the shape of " +
                        "your route. Giving it a start point places that route on the Earth.",
                    fontFamily = IdrSans,
                    color = Mute,
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                )
                Text(
                    "A point you set by hand is taken as given. Its own error is not " +
                        "known and is not included in the accuracy figure -- only the " +
                        "drift added since will be.",
                    fontFamily = IdrSans,
                    color = Accent,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                )
                OutlinedTextField(
                    value = latText,
                    onValueChange = { latText = it },
                    label = { Text("latitude (-90 to 90)") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                    colors = fieldColors,
                )
                OutlinedTextField(
                    value = lonText,
                    onValueChange = { lonText = it },
                    label = { Text("longitude (-180 to 180)") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                    colors = fieldColors,
                )
                if (haveFix) {
                    Text(
                        "Current position: %.6f, %.6f".format(hud.lat, hud.lon),
                        fontFamily = IdrMono,
                        color = Mute,
                        fontSize = 11.sp,
                    )
                } else {
                    Text(
                        "There is no position to copy from -- nothing has anchored this " +
                            "session yet.",
                        fontFamily = IdrMono,
                        color = Mute,
                        fontSize = 11.sp,
                    )
                }
                if (hud.originSource == OriginSource.USER_MAP ||
                    hud.originSource == OriginSource.USER_COORDS
                ) {
                    TextButton(onClick = onClear) {
                        Text(
                            "Remove the start point I set (back to relative)",
                            fontFamily = IdrSans,
                            color = Mute,
                            fontSize = 12.sp,
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { if (valid) onSet(lat!!, lon!!) },
                enabled = valid,
            ) {
                Text(
                    "USE THESE",
                    fontFamily = IdrMono,
                    color = if (valid) Accent else Mute,
                    fontSize = 13.sp,
                )
            }
        },
        dismissButton = {
            if (haveFix) {
                TextButton(onClick = onUseFix) {
                    Text("USE CURRENT", fontFamily = IdrMono, color = Mute, fontSize = 13.sp)
                }
            } else {
                TextButton(onClick = onDismiss) {
                    Text("CANCEL", fontFamily = IdrMono, color = Mute, fontSize = 13.sp)
                }
            }
        },
    )
}
