package `in`.sih26168.idr.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.zxing.BarcodeFormat
import com.google.zxing.DecodeHintType
import com.google.zxing.ResultPoint
import com.journeyapps.barcodescanner.BarcodeCallback
import com.journeyapps.barcodescanner.BarcodeResult
import com.journeyapps.barcodescanner.BarcodeView
import com.journeyapps.barcodescanner.DefaultDecoderFactory
import com.journeyapps.barcodescanner.camera.CameraSettings
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.pair.ConsolePairClient
import `in`.sih26168.idr.pair.PairingStore
import `in`.sih26168.idr.pair.PairingUploader
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.security.SecureRandom
import java.util.Random
import java.util.concurrent.atomic.AtomicBoolean

/** Same shape as [ConsolePairClient.parse] tokens — 8–64 url-safe chars. */
internal val PAIR_TOKEN_SHAPE = Regex("^[A-Za-z0-9_-]{8,64}$")

/** Typeable alphabet (no 0/O/1/l) that still matches [PAIR_TOKEN_SHAPE]. */
private const val PAIR_TOKEN_ALPHABET =
    "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"

internal fun isDisplayablePairToken(raw: String): Boolean =
    PAIR_TOKEN_SHAPE.matches(raw.trim())

/** Phone-minted code the console operator can type. Not an IMEI or account id. */
internal fun generatePhonePairingCode(random: Random = SecureRandom()): String =
    CharArray(16) { PAIR_TOKEN_ALPHABET[random.nextInt(PAIR_TOKEN_ALPHABET.length)] }
        .concatToString()

private const val CONSENT =
    "Pairing shares your live position with this console until you unpair. " +
        "Nothing else is sent. No account, no device ID."

/**
 * Console QR / manual pairing. Consent is shown before any scan or network call.
 *
 * **Scanner:** in-Compose [BarcodeView]. ZXing's CaptureActivity is
 * not used — it needs AppCompat and crashes under [Theme.IDR]
 * (`android:Theme.Material.NoActionBar`). Manual entry still works if the
 * camera is denied.
 *
 * Protocol matches `web.pairing.pair_payload` and `POST /ingest`
 * (`token, lat, lon, mode, speed_mps, acc_m` — never IMEI / advertising ID).
 * Works on the `standard` flavour; independent of tracker [LanUploader].
 */
@Composable
fun PairingScreen(
    bus: IdrBus,
    onBack: (() -> Unit)? = null,
) {
    val ctx = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scope = rememberCoroutineScope()
    val store = remember { PairingStore(ctx) }
    val hud by bus.hud.collectAsStateWithLifecycle()
    val pendingPair by bus.pendingPairRaw.collectAsStateWithLifecycle()

    var paired by remember { mutableStateOf(store.paired) }
    var label by remember { mutableStateOf(store.label) }
    var sessionToken by remember { mutableStateOf(store.token) }
    var consented by remember { mutableStateOf(paired) }
    var manual by remember { mutableStateOf("") }
    var fallbackBase by remember { mutableStateOf("") }
    var phoneCode by remember { mutableStateOf(generatePhonePairingCode()) }
    var status by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var scanning by remember { mutableStateOf(false) }
    var seedFromLink by remember { mutableStateOf(false) }

    fun refresh() {
        paired = store.paired
        label = store.label.ifBlank { "Paired" }
        sessionToken = store.token
        if (paired) consented = true
    }

    fun copyToken(value: String) {
        if (value.isBlank()) return
        clipboard.setText(AnnotatedString(value))
        status = "Copied"
        error = null
    }

    fun runActivate(raw: String) {
        if (busy) return
        error = null
        status = "Reaching the console…"
        busy = true
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                val parsed = ConsolePairClient.parseWithFallbackBase(
                    raw,
                    fallbackBase.takeIf { it.isNotBlank() },
                ) ?: ConsolePairClient.parse(raw)
                if (parsed == null) {
                    return@withContext ConsolePairClient.IngestResult(
                        ok = false,
                        error = "Could not read a pairing token. Paste the full console URL or code.",
                    )
                }
                if (parsed.lanBase.isNullOrBlank() && parsed.relayBase.isNullOrBlank()) {
                    return@withContext ConsolePairClient.IngestResult(
                        ok = false,
                        error = "Token alone needs a console address (e.g. http://192.168.137.1:8787).",
                    )
                }
                PairingUploader.activate(
                    context = ctx,
                    parsed = parsed,
                    lat = hud.lat,
                    lon = hud.lon,
                    mode = if (hud.gnssLock) "GNSS" else "IDR",
                    speedMps = if (hud.speedMps.isFinite()) hud.speedMps else 0.0,
                    accM = hud.accH.takeIf { it.isFinite() },
                )
            }
            busy = false
            if (result.ok) {
                status = result.label
                error = null
                refresh()
            } else {
                status = null
                error = result.error ?: "Pairing failed"
            }
        }
    }

    LaunchedEffect(pendingPair) {
        val raw = pendingPair?.trim().orEmpty()
        if (raw.isEmpty()) return@LaunchedEffect
        manual = raw
        seedFromLink = true
        bus.clearPendingPair()
    }

    LaunchedEffect(consented, seedFromLink, manual, busy, paired) {
        if (!consented || !seedFromLink || busy || paired) return@LaunchedEffect
        if (manual.isBlank()) return@LaunchedEffect
        seedFromLink = false
        runActivate(manual)
    }

    val cameraPermLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (!granted) {
            error = "Camera denied — use manual code entry below."
            return@rememberLauncherForActivityResult
        }
        scanning = true
    }

    fun startScan() {
        error = null
        val ok = ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED
        if (ok) scanning = true else cameraPermLauncher.launch(Manifest.permission.CAMERA)
    }

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Accent,
        unfocusedBorderColor = Line,
        focusedLabelColor = Accent,
        unfocusedLabelColor = Mute,
        cursorColor = Accent,
        focusedTextColor = Fg,
        unfocusedTextColor = Fg,
    )

    Box(Modifier.fillMaxSize()) {
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (onBack != null) {
                Text(
                    "← BACK",
                    modifier = Modifier
                        .defaultMinSize(minHeight = 44.dp)
                        .semantics { contentDescription = "Back" }
                        .clickable(onClick = onBack)
                        .padding(vertical = 12.dp),
                    fontFamily = IdrMono,
                    color = Accent,
                    fontSize = 11.sp,
                    letterSpacing = 1.sp,
                )
            }

            Text(
                "Connect",
                fontFamily = IdrSans,
                color = Fg,
                fontSize = 22.sp,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                "Either side can start: scan the console QR, paste its token, or show a phone code the laptop types.",
                fontFamily = IdrSans,
                color = Mute,
                fontSize = 13.sp,
                lineHeight = 18.sp,
            )

            if (paired) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(16.dp))
                        .background(Bg2)
                        .border(2.dp, Accent, RoundedCornerShape(16.dp))
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        "PAIRED",
                        fontFamily = IdrMono,
                        color = Accent,
                        fontSize = 11.sp,
                        letterSpacing = 1.5.sp,
                    )
                    Text(
                        label.ifBlank { "Paired" },
                        fontFamily = IdrSans,
                        color = Fg,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "Live position streams to this console at ~1 Hz. Underground / no radio: " +
                            "the phone keeps tracking and flushes the path when it can reach the laptop again.",
                        fontFamily = IdrSans,
                        color = Mute,
                        fontSize = 13.sp,
                        lineHeight = 18.sp,
                    )
                    if (sessionToken.isNotBlank()) {
                        Text(
                            "SESSION CODE",
                            fontFamily = IdrMono,
                            color = Telem,
                            fontSize = 11.sp,
                            letterSpacing = 1.2.sp,
                        )
                        Text(
                            sessionToken,
                            modifier = Modifier.semantics {
                                contentDescription = "Session token $sessionToken"
                            },
                            fontFamily = IdrMono,
                            color = Fg,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.sp,
                        )
                        Text(
                            "Type this on the console if the laptop asked for the phone code. " +
                                "Token only — never a device or account id.",
                            fontFamily = IdrSans,
                            color = Mute,
                            fontSize = 12.sp,
                            lineHeight = 16.sp,
                        )
                        SecondaryButton("COPY CODE", Modifier.fillMaxWidth()) {
                            copyToken(sessionToken)
                        }
                    }
                    Button(
                        onClick = {
                            PairingUploader.unpair(ctx)
                            refresh()
                            status = null
                            error = null
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp)
                            .semantics { contentDescription = "Unpair from console" },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Danger,
                            contentColor = Bg,
                        ),
                        shape = RoundedCornerShape(12.dp),
                    ) {
                        Text(
                            "UNPAIR",
                            fontFamily = IdrMono,
                            fontSize = 13.sp,
                            letterSpacing = 1.2.sp,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
            } else {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(16.dp))
                        .background(Bg2)
                        .border(1.dp, Line, RoundedCornerShape(16.dp))
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        "BEFORE YOU PAIR",
                        fontFamily = IdrMono,
                        color = Telem,
                        fontSize = 11.sp,
                        letterSpacing = 1.2.sp,
                    )
                    Text(
                        CONSENT,
                        fontFamily = IdrSans,
                        color = Fg,
                        fontSize = 15.sp,
                        lineHeight = 22.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.semantics { contentDescription = CONSENT },
                    )
                    if (!consented) {
                        Button(
                            onClick = { consented = true },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(52.dp)
                                .semantics { contentDescription = "I understand, continue to pair" },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Accent,
                                contentColor = Bg,
                            ),
                            shape = RoundedCornerShape(12.dp),
                        ) {
                            Text(
                                "I UNDERSTAND — CONTINUE",
                                fontFamily = IdrMono,
                                fontSize = 12.sp,
                                letterSpacing = 1.sp,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }

                if (consented) {
                    // ——— PRIMARY: paste the link, tap Connect. Most reliable. ———
                    Text(
                        "1. ENTER CONNECTION LINK",
                        fontFamily = IdrMono,
                        color = Accent,
                        fontSize = 11.sp,
                        letterSpacing = 1.5.sp,
                    )
                    Text(
                        "On the laptop console, tap COPY PAIRING LINK and paste it here. " +
                            "One field, one button — no camera involved.",
                        fontFamily = IdrSans,
                        color = Mute,
                        fontSize = 13.sp,
                        lineHeight = 18.sp,
                    )
                    OutlinedTextField(
                        value = manual,
                        onValueChange = { manual = it },
                        label = { Text("Pairing link or code") },
                        placeholder = { Text("http://192.168.…:8787/pair?s=…") },
                        singleLine = false,
                        minLines = 2,
                        modifier = Modifier.fillMaxWidth(),
                        colors = fieldColors,
                        shape = RoundedCornerShape(12.dp),
                    )
                    OutlinedTextField(
                        value = fallbackBase,
                        onValueChange = { fallbackBase = it },
                        label = { Text("Console address (only if you typed a bare code)") },
                        placeholder = { Text("http://192.168.137.1:8787") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        colors = fieldColors,
                        shape = RoundedCornerShape(12.dp),
                    )
                    Button(
                        onClick = { runActivate(manual) },
                        enabled = !busy && manual.isNotBlank(),
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(56.dp)
                            .semantics { contentDescription = "Connect to console" },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Accent,
                            contentColor = Bg,
                        ),
                        shape = RoundedCornerShape(12.dp),
                    ) {
                        Text(
                            if (busy) "CONNECTING…" else "CONNECT",
                            fontFamily = IdrMono,
                            fontSize = 15.sp,
                            letterSpacing = 1.4.sp,
                            fontWeight = FontWeight.Bold,
                        )
                    }

                    Spacer(Modifier.height(4.dp))

                    // ——— SECONDARY: the phone's code, for the operator to type. ———
                    Text(
                        "2. OR — SHOW THIS CODE TO THE OPERATOR",
                        fontFamily = IdrMono,
                        color = Mute,
                        fontSize = 11.sp,
                        letterSpacing = 1.5.sp,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                    Text(
                        "Read this out. The operator types it into the console — pairing " +
                            "goes the other direction.",
                        fontFamily = IdrSans,
                        color = Mute,
                        fontSize = 12.sp,
                        lineHeight = 17.sp,
                    )
                    Text(
                        phoneCode,
                        modifier = Modifier.semantics {
                            contentDescription = "Phone pairing code $phoneCode"
                        },
                        fontFamily = IdrMono,
                        color = Fg,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.4.sp,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                        SecondaryButton("COPY CODE", Modifier.weight(1f)) { copyToken(phoneCode) }
                        SecondaryButton("NEW CODE", Modifier.weight(1f)) {
                            phoneCode = generatePhonePairingCode()
                            status = null
                        }
                    }

                    // ——— TERTIARY: QR is the last resort now. ———
                    Text(
                        "3. QR (advanced)",
                        fontFamily = IdrMono,
                        color = Mute,
                        fontSize = 11.sp,
                        letterSpacing = 1.5.sp,
                        modifier = Modifier.padding(top = 12.dp),
                    )
                    SecondaryButton("SCAN CONSOLE QR", Modifier.fillMaxWidth()) { startScan() }
                }
            }

            status?.let {
                Text(it, fontFamily = IdrSans, color = Mute, fontSize = 13.sp)
            }
            error?.let {
                Text(it, fontFamily = IdrSans, color = Danger, fontSize = 13.sp, lineHeight = 18.sp)
            }

            Spacer(Modifier.height(24.dp))
        }

        if (scanning) {
            QrScanOverlay(
                onResult = { text ->
                    scanning = false
                    runActivate(text)
                },
                onDismiss = { scanning = false },
            )
        }
    }
}

@Composable
private fun QrScanOverlay(
    onResult: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val handled = remember { AtomicBoolean(false) }
    var barcodeViewRef by remember { mutableStateOf<BarcodeView?>(null) }
    var torchOn by remember { mutableStateOf(false) }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Box(
            Modifier
                .fillMaxSize()
                .background(Bg),
        ) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    BarcodeView(ctx).apply {
                        // SCENE_MODE_BARCODE is unreliable across OEMs — skipped.
                        // Continuous focus + metering is enough for a laptop QR held
                        // ~15–40 cm from the lens under normal lighting.
                        cameraSettings = CameraSettings().apply {
                            isAutoFocusEnabled = true
                            isContinuousFocusEnabled = true
                            isMeteringEnabled = true
                            isExposureEnabled = true
                        }
                        val hints = mapOf<DecodeHintType, Any>(
                            DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE),
                            DecodeHintType.TRY_HARDER to true,
                            DecodeHintType.CHARACTER_SET to "UTF-8",
                        )
                        decoderFactory = DefaultDecoderFactory(listOf(BarcodeFormat.QR_CODE), hints, "UTF-8", 2)
                        decodeContinuous(
                            object : BarcodeCallback {
                                override fun barcodeResult(result: BarcodeResult?) {
                                    val text = result?.text?.trim().orEmpty()
                                    if (text.isEmpty()) return
                                    if (!handled.compareAndSet(false, true)) return
                                    pause()
                                    post { onResult(text) }
                                }

                                override fun possibleResultPoints(resultPoints: MutableList<ResultPoint>?) = Unit
                            },
                        )
                        barcodeViewRef = this
                    }
                },
                update = { /* Lifecycle managed by DisposableEffect below. */ },
                onRelease = { view ->
                    view.pause()
                    if (barcodeViewRef === view) barcodeViewRef = null
                },
            )

            // Start the camera only after the view is attached and laid out. On
            // some devices resume() from inside AndroidView.factory races the
            // surface, leaving a black preview. DisposableEffect fires after
            // layout, and pauses cleanly when the Dialog dismisses.
            DisposableEffect(barcodeViewRef) {
                val v = barcodeViewRef
                v?.resume()
                onDispose { v?.pause() }
            }

            // Precision HUD Viewfinder Reticle
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(260.dp)
                        .border(1.dp, Line, RoundedCornerShape(16.dp)),
                ) {
                    Canvas(modifier = Modifier.fillMaxSize()) {
                        val stroke = 3.dp.toPx()
                        val arm = 24.dp.toPx()
                        val c = Accent
                        // Top-left
                        drawLine(c, Offset(0f, 0f), Offset(arm, 0f), stroke)
                        drawLine(c, Offset(0f, 0f), Offset(0f, arm), stroke)
                        // Top-right
                        drawLine(c, Offset(size.width, 0f), Offset(size.width - arm, 0f), stroke)
                        drawLine(c, Offset(size.width, 0f), Offset(size.width, arm), stroke)
                        // Bottom-left
                        drawLine(c, Offset(0f, size.height), Offset(arm, size.height), stroke)
                        drawLine(c, Offset(0f, size.height), Offset(0f, size.height - arm), stroke)
                        // Bottom-right
                        drawLine(c, Offset(size.width, size.height), Offset(size.width - arm, size.height), stroke)
                        drawLine(c, Offset(size.width, size.height), Offset(size.width, size.height - arm), stroke)
                    }
                }
            }

            // Top Bar: Torch & Close
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.TopCenter)
                    .padding(horizontal = 20.dp, vertical = 18.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    if (torchOn) "TORCH ON" else "TORCH OFF",
                    modifier = Modifier
                        .clickable {
                            torchOn = !torchOn
                            barcodeViewRef?.setTorch(torchOn)
                        }
                        .padding(8.dp),
                    fontFamily = IdrMono,
                    color = if (torchOn) Accent else Mute,
                    fontSize = 11.sp,
                    letterSpacing = 1.sp,
                )

                Text(
                    "CLOSE",
                    modifier = Modifier
                        .clickable(onClick = onDismiss)
                        .padding(8.dp)
                        .semantics { contentDescription = "Close scanner" },
                    fontFamily = IdrMono,
                    color = Accent,
                    fontSize = 12.sp,
                    letterSpacing = 1.2.sp,
                    fontWeight = FontWeight.Bold,
                )
            }

            Text(
                "ALIGN CONSOLE QR IN RETICLE",
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 36.dp),
                fontFamily = IdrMono,
                color = Fg,
                fontSize = 12.sp,
                letterSpacing = 1.2.sp,
            )
        }
    }
}
